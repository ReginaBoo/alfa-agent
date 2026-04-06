import requests
from requests.exceptions import RequestException
from app.core.config import settings
from app.auth.models import TokenData, AtlassianResource

def get_authorization_url(state: str) -> str:
    return (
        f"https://auth.atlassian.com/authorize?"
        f"audience=api.atlassian.com&"
        f"client_id={settings.ATLASSIAN_CLIENT_ID}&"
        f"scope={settings.SCOPES}&"
        f"redirect_uri={settings.ATLASSIAN_REDIRECT_URI}&"
        f"state={state}&response_type=code&prompt=consent"
    )

def exchange_code_for_token(code: str) -> TokenData:
    """Обмен кода на токен с Atlassian с обработкой ошибок"""
    try:
        resp = requests.post(
            "https://auth.atlassian.com/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": settings.ATLASSIAN_CLIENT_ID,
                "client_secret": settings.ATLASSIAN_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.ATLASSIAN_REDIRECT_URI,
            },
            timeout=10  # обязательно, чтобы не зависало
        )
        resp.raise_for_status()  # проверка HTTP-кода

        data = resp.json()
        return TokenData(**data)

    except RequestException as e:
        raise RuntimeError(f"Ошибка при получении токена: {e}") from e


# app/auth/oauth.py
def get_cloud_resources(access_token: str) -> list:
    """Получает список доступных ресурсов (сайтов)"""
    url = "https://api.atlassian.com/oauth/token/accessible-resources"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return [AtlassianResource(**r) for r in response.json()]