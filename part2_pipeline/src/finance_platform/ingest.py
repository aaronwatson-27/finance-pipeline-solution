"""Ingestion: fetch the source feed and land it into S3.

Here, `fetch_transactions` replaces what would normally be from an API/SFTP, etc.
When connecting a real source this is what would need to change. For now, this calls
generate_csv from seed.py.
"""

import logging
from datetime import date

import boto3
from botocore.config import Config

from finance_platform.seed import generate_csv

logger = logging.getLogger(__name__)

# Hardcoded for now.
LANDING_BUCKET = "finance-data-landing"
ENDPOINT = "http://localhost:4566"
REGION = "ap-southeast-2"

SEED_ROW_COUNT = 200
RANDOM_SEED = 42


def s3_client():
    """Build an S3 client (currently pointed at LocalStack).

    Path-style addressing is required because LocalStack serves every bucket
    from a single host rather than per-bucket subdomains. Credentials are dummy
    values: boto3 requires them.
    """
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(s3={"addressing_style": "path"}),
    )


def fetch_transactions(run_date: date) -> str:
    """Fetch the transaction data for a particular date.

    For now using generated data. In production this would call the source's
    API, read an SFTP drop, etc, returning the payload exactly as received,
    no transformations.
    """
    logger.info("Fetching transactions for %s from generated source", run_date)
    return generate_csv(run_date, SEED_ROW_COUNT, RANDOM_SEED)


def landing_key(run_date: date) -> str:
    """Deterministic S3 key for a business date.

    Derived from the date, so re-running a date replaces that S3 object
    rather than appending another copy.
    """
    return f"landing/finance/transactions/dt={run_date.isoformat()}/transactions.csv"


def land_raw_file(payload: str, run_date: date) -> str:
    """Write the payload to the landing S3 bucket unmodified. Returns S3 key.

    No validation happens here by design, landing stores exactly what the source sent.
    """
    key = landing_key(run_date)

    s3_client().put_object(
        Bucket=LANDING_BUCKET,
        Key=key,
        Body=payload.encode("utf-8"),
        ContentType="text/csv",
    )

    logger.info("Landed %d bytes at s3://%s/%s", len(payload), LANDING_BUCKET, key)
    return key


def read_raw_file(key: str) -> str:
    """Read a landed file back as text. Used for quality checks."""
    response = s3_client().get_object(Bucket=LANDING_BUCKET, Key=key)
    return response["Body"].read().decode("utf-8")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    run_date = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    key = land_raw_file(fetch_transactions(run_date), run_date)
    print(f"landed: {key}")
