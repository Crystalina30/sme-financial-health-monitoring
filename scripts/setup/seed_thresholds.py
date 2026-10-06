"""Seed the threshold configuration table with the default values.

Run after applying migrations:

    python scripts/setup/seed_thresholds.py

Existing rows are left untouched, so running it twice is safe.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.database import SessionLocal  # noqa: E402
from app.services.threshold_service import seed_default_thresholds  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        inserted = seed_default_thresholds(db)
        print(f"Threshold seed complete. {inserted} row(s) inserted.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
