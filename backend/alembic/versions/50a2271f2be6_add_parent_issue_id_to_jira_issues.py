"""add parent_issue_id to jira_issues

Revision ID: 50a2271f2be6
Revises: 4ea3246022f4
Create Date: 2026-05-27 19:57:34.776563

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50a2271f2be6'
down_revision: Union[str, Sequence[str], None] = '4ea3246022f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Проверяем, существует ли колонка, и добавляем только если нет
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'normalized' 
                AND table_name = 'jira_issues' 
                AND column_name = 'parent_issue_id'
            ) THEN
                ALTER TABLE normalized.jira_issues 
                ADD COLUMN parent_issue_id INTEGER;
            END IF;
        END $$;
    """)
    
    # Создаем индекс только если его нет
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE schemaname = 'normalized' 
                AND tablename = 'jira_issues' 
                AND indexname = 'ix_normalized_jira_issues_parent_issue_id'
            ) THEN
                CREATE INDEX ix_normalized_jira_issues_parent_issue_id 
                ON normalized.jira_issues(parent_issue_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем индекс
    op.drop_index(
        'ix_normalized_jira_issues_parent_issue_id',
        table_name='jira_issues',
        schema='normalized'
    )
    
    # Удаляем колонку
    op.drop_column('jira_issues', 'parent_issue_id', schema='normalized')
