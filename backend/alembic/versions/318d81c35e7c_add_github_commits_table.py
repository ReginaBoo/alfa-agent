"""add_github_commits_table

Revision ID: 318d81c35e7c
Revises: 4790b6f2a61e
Create Date: 2026-05-23 14:54:44.220968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '318d81c35e7c'
down_revision: Union[str, Sequence[str], None] = '4790b6f2a61e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('github_commits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_integration_id', sa.Integer(), nullable=True),
        sa.Column('commit_sha', sa.String(length=40), nullable=False),
        sa.Column('repo_full_name', sa.String(length=255), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=True),
        sa.Column('author_login', sa.String(length=255), nullable=True),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('author_name', sa.String(length=255), nullable=True),
        sa.Column('author_email', sa.String(length=255), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('html_url', sa.String(length=500), nullable=True),
        sa.Column('additions', sa.Integer(), nullable=True),
        sa.Column('deletions', sa.Integer(), nullable=True),
        sa.Column('total_changes', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('committed_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.Column('snapshot_version', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='normalized'
    )
    op.create_index('idx_github_commits_author', 'github_commits', ['author_login'], unique=False, schema='normalized')
    op.create_index('idx_github_commits_created', 'github_commits', ['created_at'], unique=False, schema='normalized')
    op.create_index('idx_github_commits_project', 'github_commits', ['project_id'], unique=False, schema='normalized')
    op.create_index('idx_github_commits_repo', 'github_commits', ['repo_full_name'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_github_commits_author_login'), 'github_commits', ['author_login'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_github_commits_commit_sha'), 'github_commits', ['commit_sha'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_github_commits_committed_at'), 'github_commits', ['committed_at'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_github_commits_project_id'), 'github_commits', ['project_id'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_github_commits_project_integration_id'), 'github_commits', ['project_integration_id'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_github_commits_repo_full_name'), 'github_commits', ['repo_full_name'], unique=False, schema='normalized')

def downgrade() -> None:
    op.drop_index(op.f('ix_normalized_github_commits_repo_full_name'), table_name='github_commits', schema='normalized')
    op.drop_index(op.f('ix_normalized_github_commits_project_integration_id'), table_name='github_commits', schema='normalized')
    op.drop_index(op.f('ix_normalized_github_commits_project_id'), table_name='github_commits', schema='normalized')
    op.drop_index(op.f('ix_normalized_github_commits_committed_at'), table_name='github_commits', schema='normalized')
    op.drop_index(op.f('ix_normalized_github_commits_commit_sha'), table_name='github_commits', schema='normalized')
    op.drop_index(op.f('ix_normalized_github_commits_author_login'), table_name='github_commits', schema='normalized')
    op.drop_index('idx_github_commits_repo', table_name='github_commits', schema='normalized')
    op.drop_index('idx_github_commits_project', table_name='github_commits', schema='normalized')
    op.drop_index('idx_github_commits_created', table_name='github_commits', schema='normalized')
    op.drop_index('idx_github_commits_author', table_name='github_commits', schema='normalized')
    op.drop_table('github_commits', schema='normalized')
    # ### end Alembic commands ###
