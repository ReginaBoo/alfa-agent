"""add github repo and instance id columns

Revision ID: 20260521_001
Revises: 6bd215fa2921
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20260521_001'
down_revision = '6bd215fa2921'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Добавляем github_repo и github_instance_id в таблицу core.projects"""
    
    connection = op.get_bind()
    inspector = inspect(connection)
    
    # Получаем список существующих колонок
    existing_columns = [col['name'] for col in inspector.get_columns('projects', schema='core')]
    
    # Добавляем колонку github_repo если её нет
    if 'github_repo' not in existing_columns:
        op.add_column(
            'projects', 
            sa.Column('github_repo', sa.String(255), nullable=True), 
            schema='core'
        )
        print("✓ Added column github_repo")
    else:
        print("⚠ Column github_repo already exists, skipping")
    
    # Добавляем колонку github_instance_id если её нет
    if 'github_instance_id' not in existing_columns:
        op.add_column(
            'projects', 
            sa.Column('github_instance_id', sa.Integer(), nullable=True), 
            schema='core'
        )
        print("✓ Added column github_instance_id")
    else:
        print("⚠ Column github_instance_id already exists, skipping")

def downgrade() -> None:
    """Удаляем добавленные колонки"""
    
    connection = op.get_bind()
    inspector = inspect(connection)
    
    # Получаем список существующих колонок
    existing_columns = [col['name'] for col in inspector.get_columns('projects', schema='core')]
    
    # Удаляем колонки только если они существуют
    if 'github_repo' in existing_columns:
        op.drop_column('projects', 'github_repo', schema='core')
        print("✓ Dropped column github_repo")
    
    if 'github_instance_id' in existing_columns:
        op.drop_column('projects', 'github_instance_id', schema='core')
        print("✓ Dropped column github_instance_id")