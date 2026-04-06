# app/endpoints/auth_endpoints.py
from fastapi import APIRouter, Depends, Request, Response 
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session as DbSession
from datetime import datetime, timedelta
import secrets

from app.auth.models import AtlassianResource
from app.db.models import Session as SessionModel 
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
async def callback(request: Request, db: DbSession = Depends(get_db)):
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "code not provided"}, status_code=400)

    try:
        # 1. Получаем токен
        token_data = exchange_code_for_token(code)
        
        # 2. Получаем ВСЕ ресурсы
        all_resources: list[AtlassianResource] = get_cloud_resources(token_data.access_token)
        
        if not all_resources:
            raise Exception("No accessible resources found")
        
        # 3. Определяем рабочие сайты
        working_sites = get_working_sites(token_data.access_token, all_resources)
        
        if not working_sites:
            raise Exception("Token does not work for any accessible resource")
        
        # 4. Получаем информацию о пользователе
        user_info = await get_atlassian_user_info(
            token_data.access_token, 
            working_sites[0].id
        )

        # 5. Получаем или создаем пользователя
        user = get_or_create_user(db, user_info)
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.expires_in)

        # 7. Сохраняем токены
        saved_tokens = save_tokens_for_working_sites(
            db=db,
            user_id=user.id,
            atlassian_account_id=user_info.account_id,  # ← через точку!
            token_data=token_data,
            working_sites=working_sites,
            expires_at=expires_at
        )

        session_token = secrets.token_urlsafe(32)
        session_expires = datetime.utcnow() + timedelta(days=7)

        new_session = SessionModel(
            user_id=user.id,
            session_token=session_token,
            expires_at=session_expires
        )
        db.add(new_session)
        db.commit()

        # 10. Формируем ответ
        response_data = {
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
        }

        # 11. Создаём Response с HTTP-only cookie
        response = JSONResponse(content=response_data)
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=7 * 24 * 60 * 60
        )

        return response

    except Exception as e:
        return JSONResponse(
            {"error": "Internal server error", "details": str(e)}, 
            status_code=500
        )