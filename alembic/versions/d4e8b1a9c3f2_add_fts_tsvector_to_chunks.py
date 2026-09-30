"""add_fts_tsvector_to_chunks

Revision ID: d4e8b1a9c3f2
Revises: 9c19f8694ab0
Create Date: 2026-09-02 23:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e8b1a9c3f2'
down_revision: Union[str, Sequence[str], None] = ('a1d4e22ac020', '9c19f8694ab0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add generated TSVECTOR column to chunks table in PostgreSQL
    op.add_column(
        'chunks',
        sa.Column(
            'search_vector',
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=True,
        )
    )
    # Create GIN index for fast full-text search
    op.create_index(
        'ix_chunks_search_vector',
        'chunks',
        ['search_vector'],
        unique=False,
        postgresql_using='gin',
    )


def downgrade() -> None:
    op.drop_index('ix_chunks_search_vector', table_name='chunks', postgresql_using='gin')
    op.drop_column('chunks', 'search_vector')
