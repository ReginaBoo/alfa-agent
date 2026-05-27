# alembic/versions/770244478472_add_confluence_pages_table.py

"""add confluence_pages table

Revision ID: 770244478472
Revises: df8a1a389a44
Create Date: 2026-04-16 17:48:18.908933

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '770244478472'
down_revision: Union[str, Sequence[str], None] = 'df8a1a389a44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'confluence_pages',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('space_id', sa.String(50), nullable=False),
        sa.Column('space_key', sa.String(255), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('author_id', sa.String(255), nullable=True),
        sa.Column('author_name', sa.String(255), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('parent_id', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('content_format', sa.String(50), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='normalized'
    )
    
    op.create_index('idx_confluence_pages_space', 'confluence_pages', ['space_id'], schema='normalized')
    op.create_index('idx_confluence_pages_author', 'confluence_pages', ['author_id'], schema='normalized')
    op.create_index('idx_confluence_pages_updated', 'confluence_pages', ['updated_at'], schema='normalized')


def downgrade() -> None:
    op.drop_index('idx_confluence_pages_updated', table_name='confluence_pages', schema='normalized')
    op.drop_index('idx_confluence_pages_author', table_name='confluence_pages', schema='normalized')
    op.drop_index('idx_confluence_pages_space', table_name='confluence_pages', schema='normalized')
    op.drop_table('confluence_pages', schema='normalized')