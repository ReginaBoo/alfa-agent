"""add_github_tables

Revision ID: 6a769e6b616b
Revises: 2a5405175803
Create Date: 2026-05-13 17:09:39.202481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6a769e6b616b'
down_revision: Union[str, Sequence[str], None] = '2a5405175803'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаём github_issues
    op.create_table(
        'github_issues',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_integration_id', sa.Integer(), nullable=True),
        sa.Column('issue_id', sa.Integer(), nullable=False),
        sa.Column('issue_number', sa.Integer(), nullable=False),
        sa.Column('repo_full_name', sa.String(length=255), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=False),
        sa.Column('locked', sa.Boolean(), nullable=True),
        sa.Column('author_login', sa.String(length=255), nullable=True),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('assignee_login', sa.String(length=255), nullable=True),
        sa.Column('assignee_id', sa.Integer(), nullable=True),
        sa.Column('labels', sa.JSON(), nullable=True),
        sa.Column('milestone_id', sa.Integer(), nullable=True),
        sa.Column('milestone_title', sa.String(length=255), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('comments_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.Column('snapshot_version', sa.Integer(), nullable=True),
        sa.Column('html_url', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='normalized'
    )
    
    # Индексы для github_issues
    op.create_index('idx_github_issues_repo', 'github_issues', ['repo_full_name'], schema='normalized')
    op.create_index('idx_github_issues_state', 'github_issues', ['state'], schema='normalized')
    op.create_index('idx_github_issues_assignee', 'github_issues', ['assignee_login'], schema='normalized')
    op.create_index('idx_github_issues_updated', 'github_issues', ['updated_at'], schema='normalized')
    op.create_index('ix_normalized_github_issues_issue_id', 'github_issues', ['issue_id'], schema='normalized')
    op.create_index('ix_normalized_github_issues_repo_full_name', 'github_issues', ['repo_full_name'], schema='normalized')
    
    # Создаём github_issue_events
    op.create_table(
        'github_issue_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('issue_id', sa.Integer(), nullable=False),
        sa.Column('repo_full_name', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('external_event_id', sa.Integer(), nullable=False),
        sa.Column('actor_login', sa.String(length=255), nullable=True),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('detail_login', sa.String(length=255), nullable=True),
        sa.Column('detail_id', sa.Integer(), nullable=True),
        sa.Column('commit_id', sa.String(length=40), nullable=True),
        sa.Column('commit_url', sa.String(length=500), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='normalized'
    )
    
    # Индексы для github_issue_events
    op.create_index('idx_github_events_issue', 'github_issue_events', ['issue_id'], schema='normalized')
    op.create_index('idx_github_events_event_type', 'github_issue_events', ['event_type'], schema='normalized')
    op.create_index('idx_github_events_created_at', 'github_issue_events', ['created_at'], schema='normalized')
    op.create_index('ix_normalized_github_issue_events_external_event_id', 'github_issue_events', ['external_event_id'], schema='normalized')


def downgrade() -> None:
    # Удаляем github_issue_events
    op.drop_index('ix_normalized_github_issue_events_external_event_id', table_name='github_issue_events', schema='normalized')
    op.drop_index('idx_github_events_created_at', table_name='github_issue_events', schema='normalized')
    op.drop_index('idx_github_events_event_type', table_name='github_issue_events', schema='normalized')
    op.drop_index('idx_github_events_issue', table_name='github_issue_events', schema='normalized')
    op.drop_table('github_issue_events', schema='normalized')
    
    # Удаляем github_issues
    op.drop_index('ix_normalized_github_issues_repo_full_name', table_name='github_issues', schema='normalized')
    op.drop_index('ix_normalized_github_issues_issue_id', table_name='github_issues', schema='normalized')
    op.drop_index('idx_github_issues_updated', table_name='github_issues', schema='normalized')
    op.drop_index('idx_github_issues_assignee', table_name='github_issues', schema='normalized')
    op.drop_index('idx_github_issues_state', table_name='github_issues', schema='normalized')
    op.drop_index('idx_github_issues_repo', table_name='github_issues', schema='normalized')
    op.drop_table('github_issues', schema='normalized')