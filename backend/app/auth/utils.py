from datetime import datetime, timedelta
from app.db.models import AtlassianToken
from app.auth.models import TokenData, AtlassianResource


def map_token_to_db(
    token_data: TokenData,
    user_id: int,
    atlassian_account_id: str,
    resource: AtlassianResource
) -> AtlassianToken:

    return AtlassianToken(
        user_id=user_id,
        atlassian_account_id=atlassian_account_id,
        access_token=token_data.access_token,
        refresh_token=token_data.refresh_token,
        cloud_id=resource.id,
        site_url=resource.url,
        site_name=resource.name,
        expires_at=datetime.utcnow() + timedelta(seconds=token_data.expires_in)
    )