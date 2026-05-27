"""add_github_pr_html_url

Revision ID: a1b2c3d4e5f6
Revises: 9a8b7c6d5e4f
Create Date: 2026-01-15 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9a8b7c6d5e4f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('github_pull_requests',
        sa.Column('html_url', sa.String(500), nullable=True),
        schema='normalized'
    )


def downgrade() -> None:
    op.drop_column('github_pull_requests', 'html_url', schema='normalized')
