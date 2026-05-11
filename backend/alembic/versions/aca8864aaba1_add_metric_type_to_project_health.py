"""add metric_type to project_health

Revision ID: aca8864aaba1
Revises: 9bd078dd3408
Create Date: 2026-05-11 09:44:52.171781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'aca8864aaba1'
down_revision: Union[str, Sequence[str], None] = '9bd078dd3408'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Добавляем колонку с дефолтным значением
    op.add_column(
        'project_health',
        sa.Column('metric_type', sa.String(50), nullable=False, server_default='project_health'),
        schema='public'
    )
    # Индекс для быстрых запросов
    op.create_index(
        'ix_project_health_metric_type',
        'project_health',
        ['metric_type'],
        schema='public'
    )
    # Уникальность: одна запись на тип метрики за период
    op.create_unique_constraint(
        'uq_project_health_period_type',
        'project_health',
        ['project_id', 'period_start', 'period_end', 'metric_type'],
        schema='public'
    )


def downgrade():
    op.drop_constraint(
        'uq_project_health_period_type',
        'project_health',
        schema='public',
        type_='unique'
    )
    op.drop_index('ix_project_health_metric_type', 'project_health', schema='public')
    op.drop_column('project_health', 'metric_type', schema='public')