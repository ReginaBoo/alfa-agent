"""
OAuth callback и auth эндпоинты для GitHub.
"""
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session as DbSession
from datetime import datetime, timedelta
import secrets

from app.db.session import get_db
from app.db.models import User, IntegrationToken, Session as SessionModel
from app.core.dependencies import get_current_user
from app.github.oauth import exchange_code_for_token, get_user_info, get_user_emails

router = APIRouter()


def save_github_token(db: DbSession, user_id: int, user_info: dict, token_data: dict):
    """Вспомогательная функция для сохранения GitHub токена"""
    github_username = user_info.get("login")
    github_user_id = str(user_info.get("id"))
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    
    # Удаляем старые токены GitHub для этого пользователя и инстанса
    deleted_count = db.query(IntegrationToken).filter(
        IntegrationToken.user_id == user_id,
        IntegrationToken.provider == "github",
        IntegrationToken.instance_id == github_username
    ).delete()
    
    # Сохраняем токен
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    token = IntegrationToken(
        user_id=user_id,
        provider="github",
        provider_user_id=github_user_id,
        instance_id=github_username,
        instance_name=user_info.get("name") or github_username,
        instance_url=f"https://github.com/{github_username}",
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        meta={
            "github_user_id": github_user_id,
            "github_login": github_username,
            "avatar_url": user_info.get("avatar_url")
        }
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    
    return token


@router.get("/callback")
async def github_callback(
    request: Request,
    db: DbSession = Depends(get_db)
):
    """
    Callback после GitHub OAuth авторизации.
    
    Сценарии:
    1. Пользователь уже авторизован → привязать GitHub токен к текущему пользователю
    2. Пользователь НЕ авторизован → создать нового пользователя и сессию
    """
    from app.db.models import Session as SessionModel

    code = request.query_params.get("code")
    state = request.query_params.get("state")

    
    if not code:
        return JSONResponse({"error": "code not provided"}, status_code=400)
    
    if not state:
        return JSONResponse({"error": "Invalid state"}, status_code=400)
    
    try:
        # 1. Получаем токен GitHub
        token_data = exchange_code_for_token(code)
        access_token = token_data.get("access_token")
        
        # 2. Получаем информацию о пользователе GitHub
        user_info = get_user_info(access_token)
        github_username = user_info.get("login")
        github_user_id = str(user_info.get("id"))
        
        # 3. Получаем email (для первого входа)
        emails = get_user_emails(access_token)
        primary_email = None
        for email in emails:
            if email.get("primary"):
                primary_email = email.get("email")
                break
        
        if not primary_email:
            primary_email = f"{github_username}@users.noreply.github.com"
        
        # 4. ПРОВЕРЯЕМ: есть ли активная сессия?
        session_token = request.cookies.get("session_token")
        current_user = None
        
        if session_token:
            current_user = db.query(User).join(
                SessionModel, User.id == SessionModel.user_id
            ).filter(
                SessionModel.session_token == session_token,
                SessionModel.expires_at > datetime.utcnow()
            ).first()
        
        if current_user:
            # СЦЕНАРИЙ 1: Пользователь уже авторизован → просто привязываем GitHub
            user = current_user
            token = save_github_token(db, user.id, user_info, token_data)
            
            # Возвращаем ответ без создания новой сессии
            response_data = {
                "success": True,
                "message": "GitHub account connected successfully",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.display_name,
                    "avatar_url": user.avatar_url
                },
                "instance": {
                    "instance_id": github_username,
                    "instance_name": user_info.get("name") or github_username,
                    "instance_url": f"https://github.com/{github_username}",
                    "token_id": token.id
                }
            }
            
            return JSONResponse(content=response_data)
        
        else:
            # СЦЕНАРИЙ 2: Пользователь НЕ авторизован → создаём нового
            existing_user = db.query(User).filter(
                User.email == primary_email
            ).first()
            
            if not existing_user:
                existing_user = User(
                    email=primary_email,
                    display_name=user_info.get("name") or github_username,
                    avatar_url=user_info.get("avatar_url")
                )
                db.add(existing_user)
                db.commit()
                db.refresh(existing_user)
            
            user = existing_user
            token = save_github_token(db, user.id, user_info, token_data)
            
            # Создаём сессию
            session_token_new = secrets.token_urlsafe(32)
            session_expires = datetime.utcnow() + timedelta(days=7)
            
            
            new_session = SessionModel(
                user_id=user.id,
                session_token=session_token_new,
                expires_at=session_expires
            )
            db.add(new_session)
            db.commit()
            
            # Формируем ответ
            response_data = {
                "success": True,
                "message": "Welcome! GitHub account created and connected.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.display_name,
                    "avatar_url": user.avatar_url
                },
                "instance": {
                    "instance_id": github_username,
                    "instance_name": user_info.get("name") or github_username,
                    "instance_url": f"https://github.com/{github_username}",
                    "token_id": token.id
                }
            }
            
            response = JSONResponse(content=response_data)
            response.set_cookie(
                key="session_token",
                value=session_token_new,
                httponly=True,
                secure=False,
                samesite="lax",
                max_age=7 * 24 * 60 * 60
            )
            
            return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"error": "Internal server error", "details": str(e)},
            status_code=500
        )


@router.get("/connect")
async def connect_github_for_current_user(
    request: Request,
    current_user = Depends(get_current_user),
    db: DbSession = Depends(get_db)
):
    """
    Эндпоинт для подключения GitHub к ТЕКУЩЕМУ авторизованному пользователю.
    
    Возвращает URL для OAuth авторизации с state, который будет содержать user_id.
    После callback токен будет привязан к этому пользователю.
    """
    from app.github.oauth import get_authorization_url
    import secrets
    
    # Генерируем state с user_id для последующей привязки
    state_data = {
        "user_id": current_user.id,
        "random": secrets.token_urlsafe(16)
    }
    state = secrets.token_urlsafe(32)
    
    # Сохраняем state для проверки (можно в Redis или сессию)
    # Для простоты используем только random часть в state
    auth_url = get_authorization_url(state)
    
    return {
        "success": True,
        "auth_url": auth_url,
        "state": state,
        "message": "Redirect to this URL to connect GitHub to your account"
    }


@router.get("/sites")
def get_github_sites(
    current_user=Depends(get_current_user),
    db: DbSession = Depends(get_db)
):
    """Получить список подключённых GitHub инстансов"""
    tokens = db.query(IntegrationToken).filter(
        IntegrationToken.user_id == current_user.id,
        IntegrationToken.provider == "github"
    ).all()
    
    return {
        "success": True,
        "instances": [
            {
                "instance_id": t.instance_id,
                "instance_name": t.instance_name,
                "instance_url": t.instance_url,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "token_id": t.id
            }
            for t in tokens
        ]
    }