"""Seed data must be deterministic, or the idempotency test proves nothing."""

import csv
import io
from datetime import date

from finance_platform.seed import generate_csv

RUN_DATE = date(2026, 8, 18)
ROW_COUNT = 20
SEED = 7


def _rows(csv_text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(csv_text)))


def test_same_inputs_produce_identical_output():
    """Byte-identical output is what lets the idempotency test detect real duplicates."""
    assert generate_csv(RUN_DATE, ROW_COUNT, SEED) == generate_csv(RUN_DATE, ROW_COUNT, SEED)


def test_different_seeds_produce_different_output():
    """Guards against the RNG being ignored, which would make the first test vacuous."""
    assert generate_csv(RUN_DATE, ROW_COUNT, SEED) != generate_csv(RUN_DATE, ROW_COUNT, SEED + 1)


def test_row_count_includes_defects():
    rows = _rows(generate_csv(RUN_DATE, ROW_COUNT, SEED))
    assert len(rows) == ROW_COUNT + 5


def test_expected_defects_are_present():
    """Each defect class must appear, or the quality gate is never exercised."""
    rows = _rows(generate_csv(RUN_DATE, ROW_COUNT, SEED))
    ids = [r["transaction_id"] for r in rows]

    assert any(r["transaction_id"] == "" for r in rows), "missing primary key"
    assert any(r["amount"] == "not_a_number" for r in rows), "non-numeric amount"
    assert any(r["transaction_date"] == "31/02/2026" for r in rows), "unparseable date"
    assert any(r["amount"].startswith("-") for r in rows), "negative amount"
    assert len(ids) != len(set(ids)), "duplicate primary key"
