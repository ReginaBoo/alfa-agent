"""add parent_issue_key to jira_issues

Revision ID: 5495019d7121
Revises: 50a2271f2be6
Create Date: 2026-06-17 20:32:05.070317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5495019d7121'
down_revision: Union[str, Sequence[str], None] = '50a2271f2be6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем поле parent_issue_key в таблицу jira_issues в схеме normalized
    op.add_column('jira_issues', sa.Column('parent_issue_key', sa.String(length=255), nullable=True), schema='normalized')
    
    # Создаем индекс для нового поля
    op.create_index('ix_normalized_jira_issues_parent_issue_key', 'jira_issues', ['parent_issue_key'], unique=False, schema='normalized')


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем индекс
    op.drop_index('ix_normalized_jira_issues_parent_issue_key', table_name='jira_issues', schema='normalized')
    
    # Удаляем поле
    op.drop_column('jira_issues', 'parent_issue_key', schema='normalized')