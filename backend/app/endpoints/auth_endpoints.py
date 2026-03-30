from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from app.auth.oauth import get_authorization_url, exchange_code_for_token, get_cloud_resources
from app.db.session import get_db
from app.db.models import User, AtlassianToken
from datetime import datetime, timedelta
import requests

router = APIRouter()


async def get_atlassian_user_info(access_token: str, cloud_id: str = None) -> dict:
    """Получает информацию о пользователе из Atlassian"""
    if cloud_id:
        url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/myself"
    else:
        url = "https://api.atlassian.com/me"
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return {
            "account_id": data.get("account_id") or data.get("accountId"),
            "email": data.get("email") or data.get("emailAddress"),
            "display_name": data.get("display_name") or data.get("displayName"),
            "picture": data.get("picture") or data.get("avatarUrls", {}).get("48x48")
        }
    raise Exception(f"Failed to get user info: {response.status_code}")


def get_or_create_user(db: Session, user_info: dict) -> User:
    """Получает существующего пользователя или создает нового"""
    user = db.query(User).filter(
        User.atlassian_account_id == user_info["account_id"]
    ).first()
    
    if not user:
        user = User(
            atlassian_account_id=user_info["account_id"],
            email=user_info.get("email"),
            display_name=user_info.get("display_name"),
            avatar_url=user_info.get("picture")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user


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

        # 2. Получаем ВСЕ ресурсы, к которым у приложения есть потенциальный доступ
        all_resources = get_cloud_resources(token_data.access_token)
        
        if not all_resources:
            raise Exception("No accessible resources found")
        
        # 3. Определяем, для каких сайтов ДЕЙСТВИТЕЛЬНО работает токен
        working_sites = []
        for resource in all_resources:
            try:
                test_url = f"https://api.atlassian.com/ex/jira/{resource['id']}/rest/api/3/myself"
                headers = {"Authorization": f"Bearer {token_data.access_token}"}
                response = requests.get(test_url, headers=headers, timeout=5)
                if response.status_code == 200:
                    working_sites.append(resource)
                    print(f"Token works for site: {resource['name']}")
                else:
                    print(f"Token does NOT work for site: {resource['name']} - status {response.status_code}")
            except Exception as e:
                print(f"Error testing site {resource['name']}: {e}")
        
        if not working_sites:
            raise Exception("Token does not work for any accessible resource")
        
        # 4. Получаем информацию о пользователе (через любой рабочий сайт)
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

        # 7. Сохраняем токен ТОЛЬКО для рабочих сайтов
        saved_tokens = []
        
        for resource in working_sites:
            cloud_id = resource["id"]
            site_url = resource["url"]
            site_name = resource.get("name", "")
            
            # Проверяем, есть ли уже токен для этого пользователя и сайта
            existing_token = db.query(AtlassianToken).filter(
                AtlassianToken.user_id == user.id,
                AtlassianToken.cloud_id == cloud_id
            ).first()
            
            if existing_token:
                # Обновляем существующий токен
                existing_token.access_token = token_data.access_token
                existing_token.refresh_token = token_data.refresh_token
                existing_token.expires_at = expires_at
                existing_token.site_url = site_url
                existing_token.site_name = site_name
                db.commit()
                db.refresh(existing_token)
                saved_tokens.append(existing_token)
                print(f"Updated token for site: {site_name}")
            else:
                # Создаем новый токен
                db_token = AtlassianToken(
                    user_id=user.id,
                    atlassian_account_id=user_info["account_id"],
                    access_token=token_data.access_token,
                    refresh_token=token_data.refresh_token,
                    cloud_id=cloud_id,
                    site_url=site_url,
                    site_name=site_name,
                    expires_at=expires_at
                )
                db.add(db_token)
                db.commit()
                db.refresh(db_token)
                saved_tokens.append(db_token)
                print(f"Created new token for site: {site_name}")

        # 8. Возвращаем успешный ответ
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