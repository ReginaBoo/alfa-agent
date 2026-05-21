"""add closed_at to jira_issues

Revision ID: 18f07ecc2ff4
Revises: 20260521_001
Create Date: 2026-05-21 10:19:59.513293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18f07ecc2ff4'
down_revision: Union[str, Sequence[str], None] = '20260521_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        'jira_issues',
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        schema='normalized'
    )


def downgrade():
    op.drop_column(
        'jira_issues',
        'closed_at',
        schema='normalized'
    )