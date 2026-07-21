"""Data fingerprinting for optimisation staleness detection.

Computes a snapshot of max(updated_at) per source data table to detect
when solver-input data has changed since an optimisation run started.
"""

from dataclasses import dataclass

from backend.app.db.database import get_db


@dataclass
class DataFingerprint:
    """Snapshot of max(updated_at) per source table."""

    carers_max: str | None = None  # ISO 8601 timestamp or None if table empty
    visits_max: str | None = None
    patients_max: str | None = None
    constraints_max: str | None = None

    def differs_from(self, other: "DataFingerprint") -> tuple[bool, dict[str, bool]]:
        """Compare two fingerprints.

        Returns:
            A tuple of (is_different, per_table_diff) where per_table_diff maps
            each table name to a boolean indicating whether that table's timestamp
            differs (including None vs non-None transitions).
        """
        table_diffs = {
            "carers": self.carers_max != other.carers_max,
            "visits": self.visits_max != other.visits_max,
            "patients": self.patients_max != other.patients_max,
            "constraints": self.constraints_max != other.constraints_max,
        }
        is_different = any(table_diffs.values())
        return is_different, table_diffs


class FingerprintService:
    """Computes data fingerprints from source tables."""

    async def compute(self) -> DataFingerprint:
        """Compute the current fingerprint in a single database transaction.

        Queries MAX(updated_at) from each source table (carers, visits,
        patients, constraints). Tables with no rows return None.

        Returns:
            DataFingerprint with the max updated_at for each table.
        """
        async with get_db() as db:
            carers_max = await self._get_max_updated_at(db, "carers")
            visits_max = await self._get_max_updated_at(db, "visits")
            patients_max = await self._get_max_updated_at(db, "patients")
            constraints_max = await self._get_max_updated_at(db, "constraints")

        return DataFingerprint(
            carers_max=carers_max,
            visits_max=visits_max,
            patients_max=patients_max,
            constraints_max=constraints_max,
        )

    async def _get_max_updated_at(self, db, table_name: str) -> str | None:
        """Get the maximum updated_at timestamp from a table.

        Args:
            db: Database connection.
            table_name: Name of the source data table.

        Returns:
            ISO 8601 timestamp string or None if table is empty.
        """
        cursor = await db.execute(f"SELECT MAX(updated_at) FROM {table_name}")
        row = await cursor.fetchone()
        if row and row[0]:
            return row[0]
        return None
