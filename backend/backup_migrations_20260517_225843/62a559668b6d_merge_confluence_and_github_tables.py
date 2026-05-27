"""merge_confluence_and_github_tables

Revision ID: 62a559668b6d
Revises: 6a769e6b616b, 9bd078dd3408
Create Date: 2026-05-14 08:20:46.233476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62a559668b6d'
down_revision: Union[str, Sequence[str], None] = ('6a769e6b616b', '9bd078dd3408')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
