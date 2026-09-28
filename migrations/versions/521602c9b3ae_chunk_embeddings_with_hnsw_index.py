"""chunk embeddings with hnsw index

Revision ID: 521602c9b3ae
Revises: 8b3053ba5b50
Create Date: 2026-09-23 16:56:47.798083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '521602c9b3ae'
down_revision: Union[str, Sequence[str], None] = '8b3053ba5b50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('document_chunks', sa.Column('embedding', Vector(384), nullable=True))
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.drop_column('document_chunks', 'embedding')
