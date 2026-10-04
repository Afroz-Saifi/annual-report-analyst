"""file name of each report's PDF

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: reports ingested before this column have no recorded file name
    # until the ingest command is run again.
    op.add_column("reports", sa.Column("file_name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "file_name")
