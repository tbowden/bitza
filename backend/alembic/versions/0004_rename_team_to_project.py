"""rename team to project

Revision ID: 0004_rename_team_to_project
Revises: 0003_system_config
Create Date: 2026-08-02 00:00:00.000000

Stage 6 (see bitza_open_issues.md / bitza_project_context.md): "Team" was
always just a display-label choice at the frontend (Stage 5 already
renamed the UI text to "Project") — this migration brings the backend
into line so the concept has one name everywhere, top to bottom.

Renames, in dependency order (teams -> projects first, so SQLite's
automatic foreign-key-reference update on RENAME TO already points
dependents at "projects" by the time their own columns are touched):

    teams                          -> projects
    team_members                   -> project_members
    team_members.team_id           -> project_members.project_id
    bitzas.responsible_team_id     -> bitzas.responsible_project_id
    checkouts.team_context         -> checkouts.project_context

Indexes and the one named unique constraint are explicitly dropped and
recreated under their new names rather than left with stale "team_*"
names attached to the renamed columns/tables.

Safe as a straightforward in-place rename — no production data exists
yet for this project (see bitza_context_restoration.md's testing
methodology notes). A deployment with real data would need the same
additive-then-cutover treatment any other breaking rename would.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_rename_team_to_project"
down_revision: Union[str, None] = "0003_system_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # teams -> projects
    # ------------------------------------------------------------------
    op.drop_index("ix_teams_name", table_name="teams")
    op.rename_table("teams", "projects")
    op.create_index("ix_projects_name", "projects", ["name"], unique=True)

    # ------------------------------------------------------------------
    # team_members -> project_members (incl. team_id -> project_id)
    # ------------------------------------------------------------------
    op.drop_index("ix_team_members_user_id", table_name="team_members")
    op.drop_index("ix_team_members_team_id", table_name="team_members")
    op.rename_table("team_members", "project_members")
    with op.batch_alter_table("project_members") as batch_op:
        batch_op.drop_constraint("uq_team_members_user_team", type_="unique")
        batch_op.alter_column(
            "team_id", new_column_name="project_id",
            existing_type=sa.String(36), existing_nullable=False,
        )
    # Deliberately a SEPARATE batch block from the rename above — combining
    # drop_constraint + alter_column + create_unique_constraint in a single
    # SQLite batch recreate silently drops the new constraint (verified
    # empirically against alembic 1.18.4 / SQLAlchemy 2.0.49).
    with op.batch_alter_table("project_members") as batch_op:
        batch_op.create_unique_constraint(
            "uq_project_members_user_project", ["user_id", "project_id"]
        )
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])

    # ------------------------------------------------------------------
    # bitzas.responsible_team_id -> responsible_project_id
    # ------------------------------------------------------------------
    op.drop_index("ix_bitzas_responsible_team_id", table_name="bitzas")
    with op.batch_alter_table("bitzas") as batch_op:
        batch_op.alter_column(
            "responsible_team_id", new_column_name="responsible_project_id",
            existing_type=sa.String(36), existing_nullable=False,
        )
    op.create_index(
        "ix_bitzas_responsible_project_id", "bitzas", ["responsible_project_id"]
    )

    # ------------------------------------------------------------------
    # checkouts.team_context -> project_context (free-text, no index/FK)
    # ------------------------------------------------------------------
    with op.batch_alter_table("checkouts") as batch_op:
        batch_op.alter_column(
            "team_context", new_column_name="project_context",
            existing_type=sa.String(150), existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("checkouts") as batch_op:
        batch_op.alter_column(
            "project_context", new_column_name="team_context",
            existing_type=sa.String(150), existing_nullable=True,
        )

    op.drop_index("ix_bitzas_responsible_project_id", table_name="bitzas")
    with op.batch_alter_table("bitzas") as batch_op:
        batch_op.alter_column(
            "responsible_project_id", new_column_name="responsible_team_id",
            existing_type=sa.String(36), existing_nullable=False,
        )
    op.create_index("ix_bitzas_responsible_team_id", "bitzas", ["responsible_team_id"])

    op.drop_index("ix_project_members_project_id", table_name="project_members")
    op.drop_index("ix_project_members_user_id", table_name="project_members")
    with op.batch_alter_table("project_members") as batch_op:
        batch_op.drop_constraint("uq_project_members_user_project", type_="unique")
        batch_op.alter_column(
            "project_id", new_column_name="team_id",
            existing_type=sa.String(36), existing_nullable=False,
        )
    # See matching comment in upgrade() — must stay a separate batch block.
    with op.batch_alter_table("project_members") as batch_op:
        batch_op.create_unique_constraint(
            "uq_team_members_user_team", ["user_id", "team_id"]
        )
    op.rename_table("project_members", "team_members")
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])

    op.drop_index("ix_projects_name", table_name="projects")
    op.rename_table("projects", "teams")
    op.create_index("ix_teams_name", "teams", ["name"], unique=True)
