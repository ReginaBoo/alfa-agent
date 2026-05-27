"""fix issue changelog text fields

Revision ID: 4ea3246022f4
Revises: 9a8b7c6d5e4f
Create Date: 2026-05-27 10:20:43.595458

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4ea3246022f4'
down_revision = '9a8b7c6d5e4f'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'issue_changelog',
        'from_value',
        schema='normalized',
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True
    )

    op.alter_column(
        'issue_changelog',
        'to_value',
        schema='normalized',
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True
    )


def downgrade():
    op.alter_column(
        'issue_changelog',
        'from_value',
        schema='normalized',
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True
    )

    op.alter_column(
        'issue_changelog',
        'to_value',
        schema='normalized',
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True
    )