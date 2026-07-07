"""phase 2 rebuild - teams, bitzas, checkouts, stock logs

Revision ID: 0002_bitzas
Revises: 0001_initial
Create Date: 2026-07-04 00:00:00.000000

Replaces the original 0002_assets migration outright (StorageLocation,
LocationDetail, Asset, AssetTransaction all dropped and replaced by the
unified Bitza model — see bitza_project_context.md for the full design
history). Safe as a clean rebuild since there is no production data.
Phase 1 (users, refresh_tokens) is untouched.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_bitzas"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # teams
    # ------------------------------------------------------------------
    op.create_table(
        "teams",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_teams_name", "teams", ["name"], unique=True)

    # ------------------------------------------------------------------
    # team_members
    # ------------------------------------------------------------------
    op.create_table(
        "team_members",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "team_id", sa.String(36),
            sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "team_id", name="uq_team_members_user_team"),
    )
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])

    # ------------------------------------------------------------------
    # categories
    # ------------------------------------------------------------------
    op.create_table(
        "categories",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_by", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_categories_name", "categories", ["name"], unique=True)

    # ------------------------------------------------------------------
    # bitzas
    # ------------------------------------------------------------------
    bitzakind = sa.Enum("fixed", "mobile", "stock", name="bitzakind")
    bitzastatus = sa.Enum("active", "retired", name="bitzastatus")
    retiredreason = sa.Enum(
        "lost", "broken", "discontinued", "superseded", "other", name="retiredreason"
    )
    stockmode = sa.Enum("exact", "fuzzy", name="stockmode")
    fuzzystate = sa.Enum("plentiful", "low", "empty", name="fuzzystate")

    op.create_table(
        "bitzas",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", bitzakind, nullable=False),
        sa.Column(
            "parent_id", sa.String(36),
            sa.ForeignKey("bitzas.id", ondelete="RESTRICT"), nullable=True,
        ),
        sa.Column(
            "responsible_team_id", sa.String(36),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "category_id", sa.String(36),
            sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("status", bitzastatus, nullable=False, server_default="active"),
        sa.Column("retired_reason", retiredreason, nullable=True),
        sa.Column("retired_note", sa.Text(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "retired_by_user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "purchased_by_user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("vendor", sa.String(200), nullable=True),
        sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order_url", sa.Text(), nullable=True),
        sa.Column("stock_mode", stockmode, nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=True),
        sa.Column("fuzzy_state", fuzzystate, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bitzas_name", "bitzas", ["name"])
    op.create_index("ix_bitzas_parent_id", "bitzas", ["parent_id"])
    op.create_index("ix_bitzas_responsible_team_id", "bitzas", ["responsible_team_id"])
    op.create_index("ix_bitzas_category_id", "bitzas", ["category_id"])
    op.create_index("ix_bitzas_purchased_by_user_id", "bitzas", ["purchased_by_user_id"])

    # ------------------------------------------------------------------
    # bitza_images
    # ------------------------------------------------------------------
    op.create_table(
        "bitza_images",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "bitza_id", sa.String(36),
            sa.ForeignKey("bitzas.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("image_path", sa.String(500), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "uploaded_by", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bitza_images_bitza_id", "bitza_images", ["bitza_id"])

    # ------------------------------------------------------------------
    # checkouts
    # ------------------------------------------------------------------
    op.create_table(
        "checkouts",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "bitza_id", sa.String(36),
            sa.ForeignKey("bitzas.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "holder_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("team_context", sa.String(150), nullable=True),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_checkouts_bitza_id", "checkouts", ["bitza_id"])
    op.create_index("ix_checkouts_holder_id", "checkouts", ["holder_id"])

    # ------------------------------------------------------------------
    # stock_logs
    # ------------------------------------------------------------------
    op.create_table(
        "stock_logs",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "bitza_id", sa.String(36),
            sa.ForeignKey("bitzas.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column(
            "user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stock_logs_bitza_id", "stock_logs", ["bitza_id"])
    op.create_index("ix_stock_logs_user_id", "stock_logs", ["user_id"])

    # ------------------------------------------------------------------
    # audit_logs (shape unchanged from original Phase 2)
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column(
            "user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("stock_logs")
    op.drop_table("checkouts")
    op.drop_table("bitza_images")
    op.drop_table("bitzas")
    op.drop_table("categories")
    op.drop_table("team_members")
    op.drop_table("teams")
