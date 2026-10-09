"""add bitza_documents (datasheets / SDS / manuals attached to a bitza)

Revision ID: 0005_bitza_documents
Revises: 0004_rename_team_to_project
Create Date: 2026-10-01 00:00:00.000000

Purely additive: one new table, no changes to existing ones. Files live on
the filesystem under UPLOAD_DIR (like bitza_images); this table records the
relative path plus descriptive metadata, all of it optional except the path
and size.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_bitza_documents"
down_revision: Union[str, None] = "0004_rename_team_to_project"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bitza_documents",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "bitza_id", sa.String(36),
            sa.ForeignKey("bitzas.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("doc_type", sa.String(20), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column(
            "uploaded_by", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bitza_documents_bitza_id", "bitza_documents", ["bitza_id"])


def downgrade() -> None:
    op.drop_index("ix_bitza_documents_bitza_id", table_name="bitza_documents")
    op.drop_table("bitza_documents")
