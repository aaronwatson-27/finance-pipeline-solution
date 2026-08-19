"""Ingestion: fetch the raw source data for a business date.

Here, `fetch_transactions` replaces what would normally be a set of various ingestion strategies
from multiple API/SFTP sources. When connecting real sources this is what would need to change.
For now, this calls generate_csv from seed.py.
"""

import logging
from datetime import date

from finance_platform.config import Settings
from finance_platform.seed import generate_csv

logger = logging.getLogger(__name__)


def fetch_transactions(run_date: date, settings: Settings) -> str:
    """Fetch the transaction data for a particular run_date.

    Data is generated for now, but in production this would call the source's API or read an
    SFTP drop, returning the payload as received, with no transformation.
    """
    logger.info("Fetching transactions for %s from generated source", run_date)
    return generate_csv(run_date, settings.seed_row_count, settings.random_seed)


def landing_key(run_date: date, settings: Settings, dataset: str) -> str:
    """Deterministic S3 key for a dataset and business date.

    Derived from the date alone, so re-running a date replaces that object rather
    than appending another copy.
    """
    return f"landing/{settings.domain}/{dataset}/dt={run_date.isoformat()}/{dataset}.csv"
