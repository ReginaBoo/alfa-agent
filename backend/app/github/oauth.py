"""
OAuth 2.0 интеграция с GitHub.
"""
import requests
from requests.exceptions import RequestException
from app.core.config import settings


def get_authorization_url(state: str) -> str:
    """Генерирует URL для OAuth авторизации GitHub"""
    url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={settings.GITHUB_CLIENT_ID}&"
        f"scope={settings.GITHUB_SCOPES}&"
        f"redirect_uri={settings.GITHUB_REDIRECT_URI}&"
        f"state={state}"
    )
    return url


def exchange_code_for_token(code: str) -> dict:
    """Обмен кода на токен с GitHub"""
    try:
        resp = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except RequestException as e:
        raise RuntimeError(f"Ошибка при получении токена GitHub: {e}") from e


def get_user_info(access_token: str) -> dict:
    """Получает информацию о пользователе GitHub"""
    try:
        resp = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except RequestException as e:
        raise RuntimeError(f"Ошибка при получении информации о пользователе GitHub: {e}") from e


def get_user_emails(access_token: str) -> list:
    """Получает email пользователя GitHub"""
    try:
        resp = requests.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except RequestException as e:
        # Email может быть недоступен, если scope не предоставлен
        return []


def get_repos(access_token: str, affiliation: str = "owner,collaborator,organization_member") -> list:
    """Получает список репозиториев доступных пользователю"""
    try:
        resp = requests.get(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={
                "affiliation": affiliation,
                "per_page": 100,
                "sort": "updated",
                "direction": "desc"
                # Убираем параметр "type" - он несовместим с affiliation
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except RequestException as e:
        raise RuntimeError(f"Ошибка при получении репозиториев GitHub: {e}") from e


def get_repo_issues(access_token: str, owner: str, repo: str, state: str = "all") -> list:
    """Получает issues из репозитория"""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={
                "state": state,
                "per_page": 100,
                "direction": "asc"
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except RequestException as e:
        raise RuntimeError(f"Ошибка при получении issues GitHub: {e}") from e


def get_repo_issue(access_token: str, owner: str, repo: str, issue_number: int) -> dict:
    """Получает конкретный issue"""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except RequestException as e:
        raise RuntimeError(f"Ошибка при получении issue GitHub: {e}") from e


def get_repo_issue_events(access_token: str, owner: str, repo: str, issue_number: int) -> list:
    """Получает события (events/timeline) для issue - аналог changelog"""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/events",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except RequestException as e:
        raise RuntimeError(f"Ошибка при получении событий issue GitHub: {e}") from e


def get_repo_issue_timeline(access_token: str, owner: str, repo: str, issue_number: int) -> list:
    """Получает детальную временную шкалу issue с комментариями"""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/timeline",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except RequestException as e:
        raise RuntimeError(f"Ошибка при получении timeline issue GitHub: {e}") from e
