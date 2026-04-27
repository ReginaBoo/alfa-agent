
"""
add core schema with projects and user_projects

Revision ID: 022c29ce9de4
Revises: 770244478472
Create Date: 2026-04-27 09:26:25.329362
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '022c29ce9de4'
down_revision: Union[str, Sequence[str], None] = '770244478472'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаём схему core
    op.execute("CREATE SCHEMA IF NOT EXISTS core")
    
    # Таблица projects
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('lead_account_id', sa.String(length=255), nullable=True),
        sa.Column('jira_project_key', sa.String(length=50), nullable=True),
        sa.Column('confluence_space_key', sa.String(length=255), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', name='uq_projects_key'),
        schema='core'
    )
    
    op.create_index('ix_core_projects_key', 'projects', ['key'], unique=True, schema='core')
    op.create_index('ix_core_projects_jira_project_key', 'projects', ['jira_project_key'], schema='core')
    op.create_index('ix_core_projects_lead_account_id', 'projects', ['lead_account_id'], schema='core')
    
    # Таблица user_projects
    op.create_table(
        'user_projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='viewer'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['identity.users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['core.projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'project_id', name='uq_user_project'),
        schema='core'
    )
    
    op.create_index('ix_core_user_projects_user_id', 'user_projects', ['user_id'], schema='core')
    op.create_index('ix_core_user_projects_project_id', 'user_projects', ['project_id'], schema='core')


def downgrade() -> None:
    op.drop_table('user_projects', schema='core')
    op.drop_table('projects', schema='core')
    op.execute("DROP SCHEMA IF EXISTS core CASCADE")
