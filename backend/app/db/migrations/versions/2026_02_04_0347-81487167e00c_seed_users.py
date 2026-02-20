"""seed users

Revision ID: 81487167e00c
Revises: 0f3267219977
Create Date: 2026-02-04 03:47:16.944922+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81487167e00c'
down_revision: Union[str, Sequence[str], None] = '0f3267219977'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    users_table = sa.table(
            "users",
            sa.column("id", sa.Integer),
            sa.column("email", sa.String),
            sa.column("display_name", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("hashed_password", sa.String),
            sa.column("is_superuser", sa.Boolean),
            )

    op.bulk_insert(
            users_table,
            [
                {
                    "id": 1,
                    "email": "tim.bowden@mapforge.com.au",
                    "display_name": "Tim",
                    "is_active": True,
                    "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$TrmYnhNpkIrslmvoIjTehw$PujAsgU9il2t+l5KaSPIq09nChajH7nV6FbdZGNl3dU",
                    "is_superuser": True,
                },
                {
                    "id": 2,
                    "email": "joshua.w.bowden@gmail.com",
                    "display_name": "Joshua",
                    "is_active": False,
                    "hashed_password": "x",
                    "is_superuser": False,
                },
                {
                    "id": 3,
                    "email": "jamesb1847@gmail.com",
                    "display_name": "James",
                    "is_active": False,
                    "hashed_password": "x",
                    "is_superuser": False,
                },
            ]
            )

def downgrade() -> None:
    """Downgrade schema."""
    pass
