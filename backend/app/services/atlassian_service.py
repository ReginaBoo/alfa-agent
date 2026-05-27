# app/services/atlassian_service.py
import requests
from app.core.config import settings
from app.auth.models import AtlassianResource
from app.auth.models import UserInfo


async def get_atlassian_user_info(access_token: str, cloud_id: str = None) -> UserInfo:  # ← измени тип возврата
    """Получает информацию о пользователе из Atlassian"""
    if cloud_id:
        url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/myself"
    else:
        url = "https://api.atlassian.com/me"
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    
    return UserInfo(
        account_id=data.get("account_id") or data.get("accountId"),
        email=data.get("email") or data.get("emailAddress"),
        display_name=data.get("display_name") or data.get("displayName"),
        picture=data.get("picture") or data.get("avatarUrls", {}).get("48x48")
    )


def get_working_sites(access_token: str, all_resources: list[AtlassianResource]) -> list[AtlassianResource]:
    """Определяет, для каких сайтов действительно работает токен"""
    working_sites = []
    
    for resource in all_resources:
        try:
            test_url = f"https://api.atlassian.com/ex/jira/{resource.id}/rest/api/3/myself"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(test_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                working_sites.append(resource)
                print(f"Token works for site: {resource.name}")
            else:
                print(f"Token does NOT work for site: {resource.name} - status {response.status_code}")
                
        except Exception as e:
            print(f"Error testing site {resource.name}: {e}")
    
    return working_sites