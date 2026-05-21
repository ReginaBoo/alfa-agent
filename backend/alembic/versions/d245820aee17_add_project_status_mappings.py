"""add project_status_mappings

Revision ID: d245820aee17
Revises: acc0dc74bf90
Create Date: 2026-05-21 14:16:48.525418

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd245820aee17'
down_revision: Union[str, Sequence[str], None] = 'acc0dc74bf90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        'project_status_mappings',

        sa.Column('id', sa.Integer(), primary_key=True),

        sa.Column('project_key', sa.String(255), nullable=False),
        sa.Column('status_name', sa.String(100), nullable=False),

        sa.Column('is_open', sa.Boolean(), default=True),
        sa.Column('is_in_progress', sa.Boolean(), default=False),
        sa.Column('is_closed', sa.Boolean(), default=False),

        sa.Column('jira_category', sa.String(50)),

        sa.Column('last_synced_at', sa.DateTime()),
        sa.Column('synced_by_account_id', sa.String(255)),

        sa.UniqueConstraint(
            'project_key',
            'status_name',
            name='uq_project_status'
        ),

        schema='normalized'
    )

    op.create_index(
        'idx_project_status_mappings_project',
        'project_status_mappings',
        ['project_key'],
        schema='normalized'
    )

    op.create_index(
        'idx_project_status_mappings_status',
        'project_status_mappings',
        ['status_name'],
        schema='normalized'
    )


def downgrade():
    op.drop_index(
        'idx_project_status_mappings_status',
        table_name='project_status_mappings',
        schema='normalized'
    )

    op.drop_index(
        'idx_project_status_mappings_project',
        table_name='project_status_mappings',
        schema='normalized'
    )

    op.drop_table(
        'project_status_mappings',
        schema='normalized'
    )