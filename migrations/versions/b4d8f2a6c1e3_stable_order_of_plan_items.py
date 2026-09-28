"""Stable order for plan items (position column)

Revision ID: b4d8f2a6c1e3
Revises: a7c3e1f9b2d4
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from alembic import op

revision = "b4d8f2a6c1e3"
down_revision = "a7c3e1f9b2d4"
branch_labels = None
depends_on = None

# (table, parent column). Items were read back in no particular order, so a
# ticked task could move after a save; existing rows get a stable order here.
TABLES = [("checklist_items", "module_id"), ("plan_tasks", "module_id"), ("quiz_questions", "module_id"),
          ("assessments", "module_id"), ("assessment_rubric_criteria", "assessment_id")]


def upgrade() -> None:
    for table, parent in TABLES:
        op.add_column(table, sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
        op.execute(f"""
            UPDATE {table} AS t SET position = ranked.n
            FROM (SELECT id, row_number() OVER (PARTITION BY {parent}
                         ORDER BY requirement_code NULLS LAST, id) - 1 AS n FROM {table}) AS ranked
            WHERE t.id = ranked.id
        """)


def downgrade() -> None:
    for table, _ in TABLES:
        op.drop_column(table, "position")
