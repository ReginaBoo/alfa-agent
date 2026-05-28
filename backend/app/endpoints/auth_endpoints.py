# app/endpoints/auth_endpoints.py
from fastapi import APIRouter, Depends, Request, Response 
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session as DbSession
from datetime import datetime, timedelta
import secrets
import logging


from app.auth.models import AtlassianResource
from app.db.models import Session as SessionModel, User
from app.auth.oauth import get_authorization_url, exchange_code_for_token, get_cloud_resources
from app.db.session import get_db
from app.services.atlassian_service import get_atlassian_user_info, get_working_sites
from app.services.user_service import get_or_create_user
from app.services.token_service import save_tokens_for_working_sites
from app.core.dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

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
        
        print("ALL RESOURCES:")
        for r in all_resources:
            print(r.id, r.url, r.name)

        print("WORKING SITES:")
        for r in working_sites:
            print(r.id, r.url, r.name)

        unique_sites = {}
        for site in working_sites:
            if site.id not in unique_sites:
                unique_sites[site.id] = site
        working_sites = list(unique_sites.values())
        
        print("UNIQUE WORKING SITES:")
        for r in working_sites:
            print(r.id, r.url, r.name)
        
        # 4. Получаем информацию о пользователе
        user_info = await get_atlassian_user_info(
            token_data.access_token, 
            working_sites[0].id
        )

        # 5. Получаем или создаем пользователя
        user = get_or_create_user(db, user_info)
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.expires_in)

        # Удаляем старые токены пользователя (чтобы избежать дублей)
        from app.db.models import IntegrationToken
        deleted_count = db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user.id,
            IntegrationToken.provider == "jira"
        ).delete()
        db.commit()
        print(f"Deleted {deleted_count} old tokens for user {user.id}")
        
        # 6. Сохраняем токены
        saved_tokens = save_tokens_for_working_sites(
            db=db,
            user_id=user.id,
            atlassian_account_id=user_info.account_id,
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

        # 7. Формируем ответ (без atlassian_account_id)
        response_data = {
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.display_name
            },
            "sites": [
                {
                    "cloud_id": token.instance_id,
                    "site_url": token.instance_url,
                    "site_name": token.instance_name,
                    "token_id": token.id
                }
                for token in saved_tokens
            ],
        }

        # 8. Создаём Response с HTTP-only cookie
        response = RedirectResponse(
            url="http://localhost:5173/dashboard",
            status_code=302
        )

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


@router.get("/me")
async def get_current_user_info(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Возвращает информацию о текущем пользователе"""
    # Логируем полученную cookie
    session_token = request.cookies.get("session_token")
    logger.info(f"GET /me - session_token from cookie: {session_token}")
    
    return {
        "success": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.display_name,
            "avatar_url": current_user.avatar_url
        }
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db)
):
    """Выход из системы — удаляет сессию"""
    session_token = request.cookies.get("session_token")
    
    if session_token:
        db.query(SessionModel).filter(
            SessionModel.session_token == session_token
        ).delete()
        db.commit()
    
    response.delete_cookie("session_token")
    return {"success": True, "message": "Logged out"}


@router.get("/electron-token")
async def get_electron_token(
    request: Request,
    db: DbSession = Depends(get_db)
):
    """Возвращает session_token для Electron (из cookie или заголовка)"""
    # Пробуем получить токен из cookie
    session_token = request.cookies.get("session_token")
    
    # Если нет, пробуем из заголовка
    if not session_token:
        session_token = request.headers.get("X-Session-Token")
    
    if not session_token:
        return JSONResponse({"error": "No session token"}, status_code=401)
    
    # Проверяем валидность токена
    session = db.query(SessionModel).filter(
        SessionModel.session_token == session_token,
        SessionModel.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        return JSONResponse({"error": "Invalid session"}, status_code=401)
    
    return {"session_token": session_token}

