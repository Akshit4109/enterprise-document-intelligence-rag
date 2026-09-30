"""add_hnsw_index_to_chunks

Revision ID: e5f7a28b9c10
Revises: d4e8b1a9c3f2
Create Date: 2026-09-03 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f7a28b9c10'
down_revision: Union[str, None] = 'd4e8b1a9c3f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create HNSW vector index on chunks.embedding for fast approximate nearest neighbor cosine retrieval
    op.create_index(
        'ix_chunks_embedding_hnsw_cosine',
        'chunks',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    # Drop only the HNSW vector index on chunks.embedding
    op.drop_index(
        'ix_chunks_embedding_hnsw_cosine',
        table_name='chunks',
        postgresql_using='hnsw',
    )
