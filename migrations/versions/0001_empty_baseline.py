"""Establish the empty Gateway migration baseline."""

from collections.abc import Sequence

revision: str = "0001_empty_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create no domain tables."""


def downgrade() -> None:
    """Remove no domain tables."""
