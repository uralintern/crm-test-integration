"""Очищает таблицу стажировок в БД перед запуском ETL."""
import logging
import sys
from pathlib import Path

from ETL.logging_config import get_logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.internships_db import internships_db

logger = get_logger(__name__)


def clear_json_dirs():
    base = Path(__file__).parent / "data"
    dirs = ["parsed", "transformed"]
    total = 0
    for d in dirs:
        target = base / d
        if not target.exists():
            continue
        for f in target.glob("*.json"):
            try:
                logger.info("Deleting file: %s", f)
                f.unlink()
                total += 1
            except Exception as e:
                logger.error("[ERROR] Failed to delete %s: %s", f, e)
    logger.info("[OK] Deleted %d JSON files from data/parsed and data/transformed", total)


def main():
    logger.info("=" * 60)
    logger.info("Clearing database before ETL")
    logger.info("=" * 60)

    db_ok = False
    try:
        logger.info("Starting database cleanup")
        count = internships_db.clear()
        logger.info("[OK] Deleted %d records from internships table", count)
        db_ok = True
    except Exception as e:
        logger.error("[ERROR] Failed to clear database: %s", e)
        raise

    if db_ok:
        clear_json_dirs()

    logger.info("=" * 60)
    logger.info("Database cleared successfully")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    logger.info("clear_db script started")
    sys.exit(main())
