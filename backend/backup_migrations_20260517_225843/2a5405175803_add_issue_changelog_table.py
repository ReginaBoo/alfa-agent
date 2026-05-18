"""add issue_changelog table

Revision ID: 2a5405175803
Revises: 022c29ce9de4
Create Date: 2026-04-27 10:02:46.512881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2a5405175803'
down_revision: Union[str, Sequence[str], None] = '022c29ce9de4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'issue_changelog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('issue_key', sa.String(length=255), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('from_value', sa.String(length=255), nullable=True),
        sa.Column('to_value', sa.String(length=255), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.Column('author_account_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        schema='normalized'
    )
    
    op.create_index('idx_changelog_issue_key', 'issue_changelog', ['issue_key'], schema='normalized')
    op.create_index('idx_changelog_field', 'issue_changelog', ['field_name'], schema='normalized')
    op.create_index('idx_changelog_changed_at', 'issue_changelog', ['changed_at'], schema='normalized')


def downgrade() -> None:
    op.drop_table('issue_changelog', schema='normalized')