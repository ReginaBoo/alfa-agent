from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from app.auth.oauth import get_authorization_url, exchange_code_for_token, get_cloud_id
from app.db.session import get_db
from app.db.models import Token
from datetime import datetime
import requests

router = APIRouter()

USER_ID = "test_user"  # пока упрощённо

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
        return JSONResponse({"error": "code не передан"}, status_code=400)

    try:
        # Получаем токен
        token_data = exchange_code_for_token(code)

        # Получаем cloud_id
        cloud_id = get_cloud_id(token_data.access_token)

        # Считаем дату истечения
        expires_at = None
        if hasattr(token_data, "expires_in"):
            from datetime import datetime, timedelta
            expires_at = datetime.utcnow() + timedelta(seconds=token_data.expires_in)

        # Сохраняем в БД
        db_token = Token(
            user_id=USER_ID,  # пока упрощённо
            access_token=token_data.access_token,
            refresh_token=token_data.refresh_token,
            cloud_id=cloud_id,
            site_url="",  # при необходимости можно получить через API Atlassian
            expires_at=expires_at
        )
        db.add(db_token)
        db.commit()
        db.refresh(db_token)

        return {
            "access_token": token_data.access_token,
            "refresh_token": token_data.refresh_token,
            "cloud_id": cloud_id,
            "expires_in": token_data.expires_in,
            "scope": token_data.scope,
            "db_id": db_token.id  # чтобы видеть, что записалось
        }

    except requests.exceptions.RequestException as e:
        return JSONResponse({"error": "Ошибка запроса к Atlassian", "details": str(e)}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": "Внутренняя ошибка сервера", "details": str(e)}, status_code=500)