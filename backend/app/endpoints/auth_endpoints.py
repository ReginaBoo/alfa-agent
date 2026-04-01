# app/endpoints/auth_endpoints.py
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.auth.oauth import get_authorization_url, exchange_code_for_token, get_cloud_resources
from app.db.session import get_db
from app.services.atlassian_service import get_atlassian_user_info, get_working_sites
from app.services.user_service import get_or_create_user
from app.services.token_service import save_tokens_for_working_sites

router = APIRouter()


@router.get("/login")
def login():
    state = "test_state"
    url = get_authorization_url(state)
    return RedirectResponse(url)


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        return JSONResponse({"error": "code not provided"}, status_code=400)

    try:
        # 1. Получаем токен
        token_data = exchange_code_for_token(code)

        # 2. Получаем ВСЕ ресурсы
        all_resources = get_cloud_resources(token_data.access_token)
        
        if not all_resources:
            raise Exception("No accessible resources found")
        
        # 3. Определяем рабочие сайты
        working_sites = get_working_sites(token_data.access_token, all_resources)
        
        if not working_sites:
            raise Exception("Token does not work for any accessible resource")
        
        # 4. Получаем информацию о пользователе
        user_info = await get_atlassian_user_info(
            token_data.access_token, 
            working_sites[0]["id"]
        )

        # 5. Получаем или создаем пользователя
        user = get_or_create_user(db, user_info)

        # 6. Рассчитываем expires_at
        expires_at = None
        if hasattr(token_data, "expires_in"):
            expires_at = datetime.utcnow() + timedelta(seconds=token_data.expires_in)

        # 7. Сохраняем токены
        saved_tokens = save_tokens_for_working_sites(
            db=db,
            user_id=user.id,
            atlassian_account_id=user_info["account_id"],
            token_data=token_data,
            working_sites=working_sites,
            expires_at=expires_at
        )

        # 8. Возвращаем ответ
        return {
            "success": True,
            "user": {
                "id": user.id,
                "account_id": user.atlassian_account_id,
                "email": user.email,
                "name": user.display_name
            },
            "sites": [
                {
                    "cloud_id": token.cloud_id,
                    "site_url": token.site_url,
                    "site_name": token.site_name,
                    "token_id": token.id
                }
                for token in saved_tokens
            ],
            "other_available_sites": [
                {
                    "cloud_id": r["id"],
                    "site_url": r["url"],
                    "site_name": r.get("name", "")
                }
                for r in all_resources if r["id"] not in [s.cloud_id for s in saved_tokens]
            ],
            "access_token": token_data.access_token,
            "refresh_token": token_data.refresh_token,
            "expires_in": token_data.expires_in,
            "scope": token_data.scope
        }

    except Exception as e:
        return JSONResponse(
            {"error": "Internal server error", "details": str(e)}, 
            status_code=500
        )