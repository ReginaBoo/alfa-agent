"""add_github_pull_requests_and_reviews

Revision ID: 9a8b7c6d5e4f
Revises: 318d81c35e7c
Create Date: 2026-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a8b7c6d5e4f'
down_revision = '318d81c35e7c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================== PULL REQUESTS ====================
    op.create_table('github_pull_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_integration_id', sa.Integer(), nullable=True),
        
        # Основной идентификатор
        sa.Column('pr_id', sa.Integer(), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('repo_full_name', sa.String(255), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=True),
        
        # Информация о PR
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('state', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),  # open/closed/merged
        
        # Автор и назначенные
        sa.Column('author_login', sa.String(255), nullable=True),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('mergeable', sa.Boolean(), nullable=True),
        sa.Column('mergeable_state', sa.String(50), nullable=True),
        
        # Ревьюверы (JSON массив логинов)
        sa.Column('requested_reviewers', sa.JSON(), nullable=True),
        
        # Даты
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('merged_at', sa.DateTime(), nullable=True),
        sa.Column('merged', sa.Boolean(), default=False),
        sa.Column('merged_by_login', sa.String(255), nullable=True),
        sa.Column('merged_by_id', sa.Integer(), nullable=True),
        
        # Статистика
        sa.Column('comments_count', sa.Integer(), default=0),
        sa.Column('review_comments_count', sa.Integer(), default=0),
        sa.Column('commits_count', sa.Integer(), default=0),
        sa.Column('additions', sa.Integer(), default=0),
        sa.Column('deletions', sa.Integer(), default=0),
        
        # Связи
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('head_branch', sa.String(255), nullable=True),
        sa.Column('base_branch', sa.String(255), nullable=True),
        sa.Column('head_sha', sa.String(40), nullable=True),
        
        # Временные метки синхронизации
        sa.Column('last_synced_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('snapshot_version', sa.Integer(), default=1),
        
        sa.Column('html_url', sa.String(500), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        schema='normalized'
    )
    
    # Индексы для github_pull_requests
    with op.batch_alter_table('github_pull_requests', schema='normalized') as batch_op:
        batch_op.create_index('idx_github_pr_repo', ['repo_full_name'])
        batch_op.create_index('idx_github_pr_author', ['author_login'])
        batch_op.create_index('idx_github_pr_state', ['state'])
        batch_op.create_index('idx_github_pr_merged_at', ['merged_at'])
        batch_op.create_index('idx_github_pr_project', ['project_id'])
        batch_op.create_index('ix_github_pull_requests_pr_id', ['pr_id'], unique=True)
    
    # ==================== PULL REQUEST REVIEWS ====================
    op.create_table('github_pull_request_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_integration_id', sa.Integer(), nullable=True),
        
        # Идентификаторы
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('pr_id', sa.Integer(), nullable=False),
        sa.Column('repo_full_name', sa.String(255), nullable=False),
        
        # Информация о ревью
        sa.Column('user_login', sa.String(255), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('state', sa.String(50), nullable=False),  # APPROVED/CHANGES_REQUESTED/COMMENTED
        sa.Column('body', sa.Text(), nullable=True),
        
        # Даты
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        
        # Ссылки
        sa.Column('html_url', sa.String(500), nullable=True),
        sa.Column('pull_request_url', sa.String(500), nullable=True),
        
        # Временные метки
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('last_synced_at', sa.DateTime(), default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        schema='normalized'
    )
    
    # Индексы для github_pull_request_reviews
    with op.batch_alter_table('github_pull_request_reviews', schema='normalized') as batch_op:
        batch_op.create_index('idx_github_pr_reviews_pr', ['pr_id'])
        batch_op.create_index('idx_github_pr_reviews_user', ['user_login'])
        batch_op.create_index('idx_github_pr_reviews_state', ['state'])
        batch_op.create_index('ix_github_pull_request_reviews_review_id', ['review_id'], unique=True)


def downgrade() -> None:
    op.drop_table('github_pull_request_reviews', schema='normalized')
    op.drop_table('github_pull_requests', schema='normalized')
