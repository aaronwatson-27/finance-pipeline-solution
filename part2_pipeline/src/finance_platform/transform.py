"""Transform validated transactions into daily aggregates per category.

Using DuckDB as the compute engine for aggregation and parquet write.
Output is written to a local temporary directory first, then uploaded — staging locally separates
the failure modes: SQL error or upload error. Also prevents a failed aggregation from leaving a
half-written partition in the curated bucket.

Re-runs are idempotent because the target partition is deleted before uploading, so running a date
twice produces the same output rather than accumulating. Only the partition for that specific run
date is touched — other dates are left alone.
"""

import csv
import io
import logging
import tempfile
from datetime import date
from pathlib import Path

import duckdb

from finance_platform.config import Settings
from finance_platform.s3 import delete_prefix, upload_file

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).parent / "sql"


def load_sql(name: str) -> str:
    """Read a query from the sql/ directory alongside this module."""
    return (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")


def _convert_accepted_rows_to_csv(accepted: list) -> str:
    """Converted validated models back to CSV for DuckDB to read.

    Fields come from the model itself via `model_dump`, so this works for any
    Pydantic schema.
    """
    rows = [model.model_dump(mode="json") for model in accepted]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def build_transactions_curated(accepted: list, run_date: date, settings: Settings) -> list[str]:
    """Aggregate accepted transaction rows and write partitioned Parquet files to
    the curated data layer. Returns the list of S3 keys written.

    The target partition is deleted before writing, so re-running a date produces
    the same result rather than accumulating files.
    """
    if not accepted:
        logger.warning("No accepted rows for %s; nothing to write", run_date)
        return []

    curated_prefix = settings.curated_prefix
    partition_prefix = f"{curated_prefix}/transaction_date={run_date.isoformat()}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source_csv = tmp_path / "accepted.csv"
        source_csv.write_text(_convert_accepted_rows_to_csv(accepted), encoding="utf-8")

        output_dir = tmp_path / "out"

        con = duckdb.connect()
        try:
            # Define the aggregation as a view so the source path is bound once.
            # DuckDB will not accept a bound parameter inside COPY (...).
            sql = load_sql("daily_category_spend").replace("$source_path", f"'{source_csv}'")

            con.execute(f"CREATE TEMP VIEW aggregated AS {sql}")

            # output_dir is interpolated rather than bound: COPY requires a literal
            # target. The path comes from tempfile, so there is no SQL injection risk.
            con.execute(
                f"""
                COPY aggregated
                TO '{output_dir}'
                (FORMAT PARQUET, PARTITION_BY (transaction_date, category),
                 OVERWRITE_OR_IGNORE, COMPRESSION ZSTD)
                """
            )

            row_count = con.execute("SELECT COUNT(*) FROM aggregated").fetchone()[0]
        finally:
            con.close()

        logger.info("Aggregated to %d category rows for %s", row_count, run_date)

        # Clear the partition before upload, so a re-run replaces the files.
        delete_prefix(settings.curated_bucket, partition_prefix, settings)

        written: list[str] = []
        for parquet in sorted(output_dir.rglob("*.parquet")):
            key = f"{curated_prefix}/{parquet.relative_to(output_dir).as_posix()}"
            upload_file(settings.curated_bucket, key, str(parquet), settings)
            written.append(key)

    logger.info(
        "Wrote %d parquet files to s3://%s/%s",
        len(written),
        settings.curated_bucket,
        partition_prefix,
    )
    return written
