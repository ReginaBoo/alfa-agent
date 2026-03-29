import requests


def get_accessible_resources(access_token: str):
    url = "https://api.atlassian.com/oauth/token/accessible-resources"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)
    return response.json()