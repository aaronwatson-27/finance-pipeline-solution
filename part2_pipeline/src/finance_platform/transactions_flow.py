"""Prefect Orchestration

Runs tasks to fetch data, land it in the S3 landing bucket, validate, quarantine rejected records,
and transform into an aggregated view.

The business date is a parameter, so any date can be re-run at any time and produce the same result.

Retries are used for tasks that make network calls (the fetch and S3 reads and writes), because
these can potentially succeed on the next attempt.
"""

from datetime import date

from prefect import flow, get_run_logger, task

from finance_platform.config import Settings, get_settings
from finance_platform.ingest import fetch_transactions, landing_key
from finance_platform.quality import Transaction, parse_csv, to_csv, validate_rows
from finance_platform.s3 import read_text, write_csv
from finance_platform.transform import build_transactions_curated

REJECT_FIELDNAMES = [*Transaction.model_fields, "reject_reason"]

DATASET = "transactions"


def quarantine_key(run_date: date, settings: Settings, dataset: str) -> str:
    """Where rejected rows for a dataset and business date are written."""
    return f"quarantine/{settings.domain}/{dataset}/dt={run_date.isoformat()}/rejects.csv"


@task(retries=3, retry_delay_seconds=2)
def fetch_and_land(run_date: date, settings: Settings) -> str:
    """Fetch the source data and write it to landing unmodified."""
    payload = fetch_transactions(run_date, settings)
    return write_csv(
        settings.landing_bucket,
        landing_key(run_date, settings, dataset=DATASET),
        payload,
        settings,
    )


@task(retries=3, retry_delay_seconds=2)
def read_landed(key: str, settings: Settings) -> str:
    return read_text(settings.landing_bucket, key, settings)


@task
def apply_quality_gate(payload: str) -> tuple[list, list[dict]]:
    """Split parsed rows into accepted and rejected. No retries: validation is deterministic."""
    return validate_rows(parse_csv(payload))


@task(retries=3, retry_delay_seconds=2)
def quarantine_rejects(rejected: list[dict], run_date: date, settings: Settings) -> str | None:
    """Write rejected rows with their reasons to quarantine folder, so they can be inspected and
    replayed.

    Empty file still written, 'no file' means the run failed, not 'clean run'
    """
    return write_csv(
        settings.landing_bucket,
        quarantine_key(run_date, settings, dataset=DATASET),
        to_csv(rejected, REJECT_FIELDNAMES),
        settings,
    )


@task(retries=2, retry_delay_seconds=2)
def write_curated(accepted: list, run_date: date, settings: Settings) -> list[str]:
    return build_transactions_curated(accepted, run_date, settings)


@flow(name="finance-daily-transactions")
def finance_daily(run_date: date) -> dict:
    """Run the daily finance pipeline for a specified business date (required)."""

    settings = get_settings()
    logger = get_run_logger()
    logger.info("Starting run for %s", run_date)

    landed = fetch_and_land(run_date, settings)
    payload = read_landed(landed, settings)
    accepted, rejected = apply_quality_gate(payload)

    quarantined = quarantine_rejects(rejected, run_date, settings)
    curated_keys = write_curated(accepted, run_date, settings)

    summary = {
        "run_date": run_date.isoformat(),
        "landed_key": landed,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "quarantine_key": quarantined,
        "curated_files": len(curated_keys),
    }
    logger.info("Run complete: %s", summary)
    return summary


if __name__ == "__main__":
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    finance_daily(date.fromisoformat(arg) if arg else date.today())
