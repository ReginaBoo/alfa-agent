"""add closed_at to jira issues

Revision ID: acc0dc74bf90
Revises: 18f07ecc2ff4
Create Date: 2026-05-21 10:35:29.534729

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'acc0dc74bf90'
down_revision: Union[str, Sequence[str], None] = '18f07ecc2ff4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'jira_issues',
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        schema='normalized'
    )

    op.create_index(
        'ix_normalized_jira_issues_closed_at',
        'jira_issues',
        ['closed_at'],
        unique=False,
        schema='normalized'
    )


def downgrade() -> None:
    op.drop_index(
        'ix_normalized_jira_issues_closed_at',
        table_name='jira_issues',
        schema='normalized'
    )

    op.drop_column(
        'jira_issues',
        'closed_at',
        schema='normalized'
    )