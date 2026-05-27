"""add github fields to projects

Revision ID: 20260514_001
Revises: 62a559668b6d
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260514_001'
down_revision = '62a559668b6d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавляем колонки в таблицу core.projects"""
    
    # Добавляем колонку github_repo
    op.add_column(
        'projects', 
        sa.Column('github_repo', sa.String(255), nullable=True),
        schema='core'
    )
    
    # Добавляем колонку github_instance_id
    op.add_column(
        'projects', 
        sa.Column('github_instance_id', sa.Integer(), nullable=True),
        schema='core'
    )
    
    # Добавляем колонку confluence_space_key (если нет)
    op.add_column(
        'projects', 
        sa.Column('confluence_space_key', sa.String(100), nullable=True),
        schema='core'
    )
    
    # Добавляем колонку lead_account_id (если нет)
    op.add_column(
        'projects', 
        sa.Column('lead_account_id', sa.String(255), nullable=True),
        schema='core'
    )


def downgrade() -> None:
    """Удаляем добавленные колонки"""
    
    op.drop_column('projects', 'github_repo', schema='core')
    op.drop_column('projects', 'github_instance_id', schema='core')
    op.drop_column('projects', 'confluence_space_key', schema='core')
    op.drop_column('projects', 'lead_account_id', schema='core')