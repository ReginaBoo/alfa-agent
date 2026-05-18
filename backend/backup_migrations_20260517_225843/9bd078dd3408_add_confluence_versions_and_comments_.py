"""add confluence versions and comments tables

Revision ID: 9bd078dd3408
Revises: 2a5405175803
Create Date: 2026-04-29 15:14:20.536252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bd078dd3408'
down_revision: Union[str, Sequence[str], None] = '2a5405175803'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# alembic/versions/9bd078dd3408_add_confluence_versions_and_comments_.py

def upgrade() -> None:
    """Upgrade schema — только новые таблицы для Confluence"""
    
    # === ConfluencePageVersion ===
    op.create_table(
        'confluence_page_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('page_id', sa.String(length=50), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('author_id', sa.String(length=255), nullable=True),
        sa.Column('author_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('minor_edit', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='normalized'
    )
    op.create_index('idx_page_versions_page', 'confluence_page_versions', ['page_id', 'version_number'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_confluence_page_versions_author_id'), 'confluence_page_versions', ['author_id'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_confluence_page_versions_page_id'), 'confluence_page_versions', ['page_id'], unique=False, schema='normalized')
    
    # === ConfluenceComment ===
    op.create_table(
        'confluence_comments',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('page_id', sa.String(length=50), nullable=False),
        sa.Column('author_id', sa.String(length=255), nullable=True),
        sa.Column('author_name', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=True),
        sa.Column('parent_id', sa.String(length=50), nullable=True),
        sa.Column('position', sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='normalized'
    )
    op.create_index('idx_comments_author', 'confluence_comments', ['author_id'], unique=False, schema='normalized')
    op.create_index('idx_comments_page', 'confluence_comments', ['page_id'], unique=False, schema='normalized')
    op.create_index('idx_comments_resolved', 'confluence_comments', ['is_resolved'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_confluence_comments_author_id'), 'confluence_comments', ['author_id'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_confluence_comments_is_resolved'), 'confluence_comments', ['is_resolved'], unique=False, schema='normalized')
    op.create_index(op.f('ix_normalized_confluence_comments_page_id'), 'confluence_comments', ['page_id'], unique=False, schema='normalized')


def downgrade() -> None:
    """Downgrade schema — только новые таблицы для Confluence"""
    
    # === ConfluenceComment ===
    op.drop_index(op.f('ix_normalized_confluence_comments_page_id'), table_name='confluence_comments', schema='normalized')
    op.drop_index(op.f('ix_normalized_confluence_comments_is_resolved'), table_name='confluence_comments', schema='normalized')
    op.drop_index(op.f('ix_normalized_confluence_comments_author_id'), table_name='confluence_comments', schema='normalized')
    op.drop_index('idx_comments_resolved', table_name='confluence_comments', schema='normalized')
    op.drop_index('idx_comments_page', table_name='confluence_comments', schema='normalized')
    op.drop_index('idx_comments_author', table_name='confluence_comments', schema='normalized')
    op.drop_table('confluence_comments', schema='normalized')
    
    # === ConfluencePageVersion ===
    op.drop_index(op.f('ix_normalized_confluence_page_versions_page_id'), table_name='confluence_page_versions', schema='normalized')
    op.drop_index(op.f('ix_normalized_confluence_page_versions_author_id'), table_name='confluence_page_versions', schema='normalized')
    op.drop_index('idx_page_versions_page', table_name='confluence_page_versions', schema='normalized')
    op.drop_table('confluence_page_versions', schema='normalized')
