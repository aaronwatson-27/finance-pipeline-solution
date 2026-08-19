"""Tests for end-to-end idempotency of pipeline

Requires a running LocalStack with buckets applied: make up && make tf-apply.
"""

import hashlib
from datetime import date

import pytest
import requests
from finance_platform.config import get_settings
from finance_platform.s3 import delete_prefix, list_keys, read_text, s3_client
from finance_platform.transactions_flow import DATASET, finance_daily, quarantine_key

pytestmark = pytest.mark.localstack

RUN_DATE = date(2027, 3, 15)  # Arbitrary date

SETTINGS = get_settings()
PARTITION_PREFIX = f"{SETTINGS.curated_prefix}/transaction_date={RUN_DATE.isoformat()}"


def _localstack_available() -> bool:
    """Confirms localstack is up"""
    try:
        requests.get(f"{SETTINGS.localstack_endpoint}/_localstack/health", timeout=2)
        return True
    except requests.RequestException:
        return False


def _fingerprint_prefix(prefix: str) -> dict[str, str]:
    """Map every curated key under a prefix to a hash of its contents.
    Lets us catch differences in bytes, not just a change in file count.
    """
    client = s3_client(SETTINGS)
    return {
        key: hashlib.sha256(
            client.get_object(Bucket=SETTINGS.curated_bucket, Key=key)["Body"].read()
        ).hexdigest()
        for key in sorted(list_keys(SETTINGS.curated_bucket, prefix, SETTINGS))
    }


@pytest.fixture(scope="module", autouse=True)
def clean_partition():
    """Start from an empty partition so the test does not depend on previous runs."""
    if not _localstack_available():
        pytest.skip("LocalStack not running — run 'make up' and 'make tf-apply'")

    delete_prefix(SETTINGS.curated_bucket, PARTITION_PREFIX, SETTINGS)
    yield
    delete_prefix(SETTINGS.curated_bucket, PARTITION_PREFIX, SETTINGS)


def test_first_run_produces_expected_output():
    """First run test: gate rejects the five deliberate defects and nothing else."""
    result = finance_daily(RUN_DATE)

    assert result["accepted"] == 200
    assert result["rejected"] == 5
    assert result["curated_files"] == 6  # one parquet file per category


def test_second_run_produces_identical_curated_output():
    """Checking idempotency: for the same date, we get same bytes, no accumulation of files."""
    finance_daily(RUN_DATE)
    first = _fingerprint_prefix(PARTITION_PREFIX)

    finance_daily(RUN_DATE)
    second = _fingerprint_prefix(PARTITION_PREFIX)

    assert first == second, "curated output changed between identical runs"
    assert len(second) == 6, "partition accumulated files across runs"


def test_landing_object_is_replaced_not_duplicated():
    """Runs same date twice, confirms only one transactions.csv after second run"""
    finance_daily(RUN_DATE)
    finance_daily(RUN_DATE)

    expected = f"landing/finance/transactions/dt={RUN_DATE.isoformat()}/transactions.csv"
    keys = list_keys(
        SETTINGS.landing_bucket,
        f"landing/finance/transactions/dt={RUN_DATE.isoformat()}/",
        SETTINGS,
    )
    assert keys == [expected]


def test_quarantine_content_is_stable_across_runs():
    """Checks that rejects are reproducible too."""
    key = quarantine_key(RUN_DATE, SETTINGS, dataset=DATASET)

    finance_daily(RUN_DATE)
    first = read_text(SETTINGS.landing_bucket, key, SETTINGS)

    finance_daily(RUN_DATE)
    second = read_text(SETTINGS.landing_bucket, key, SETTINGS)

    assert first == second
    assert first.count("\n") == 6  # header + five rejects


def test_other_dates_are_untouched():
    """A re-run should only rewrite its own partition. Without this, a backfill could silently
    destroy the rest of the history."""
    other_date = date(2027, 3, 14)
    other_prefix = f"{SETTINGS.curated_prefix}/transaction_date={other_date.isoformat()}"

    try:
        finance_daily(other_date)
        before = _fingerprint_prefix(other_prefix)

        finance_daily(RUN_DATE)
        after = _fingerprint_prefix(other_prefix)

        assert before == after, "re-running one date modified another"
        assert len(after) == 6
    finally:
        delete_prefix(SETTINGS.curated_bucket, other_prefix, SETTINGS)
