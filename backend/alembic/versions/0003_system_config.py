"""system config - singleton root bitza pointer

Revision ID: 0003_system_config
Revises: 0002_bitzas
Create Date: 2026-07-24 00:00:00.000000

Adds a single-row system_config table pointing at the one permanent root
bitza, rather than adding an is_root-style column to every bitzas row.
See app/models/system_config.py's docstring for the full rationale.

Also tightens bitzas.parent_id: at the application layer, ordinary
creates (POST /bitzas/) now always require a parent — see
BitzaCreate.parent_id and BitzaService.create_bitza. The column itself
stays nullable at the DB level (the one existing root row, and any
future direct-DB bootstrap, still needs parent_id IS NULL to be valid) —
this migration does not change the bitzas table at all, only adds the
new pointer table.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_system_config"
down_revision: Union[str, None] = "0002_bitzas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "root_bitza_id", sa.String(36),
            sa.ForeignKey("bitzas.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_system_config_singleton"),
        sa.UniqueConstraint("root_bitza_id", name="uq_system_config_root_bitza_id"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_config")
