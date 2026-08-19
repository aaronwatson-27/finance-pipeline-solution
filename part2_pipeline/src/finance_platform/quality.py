"""Quality validation using pydantic: validate landed rows and separate defective rows.

Based on two types of defect:
    a) Structural defect: the row cannot be interpreted at all. Missing primary key, an amount that
    is not a number, a date in the wrong format.

    b) Business rule: the row parses but violates a rule, e.g., negative amount, duplicate PK

Rejected rows are returned with a reason attached, and will be sent to a quarantine folder in
landing where they can be checked and potentially replayed.
"""

import csv
import io
import logging
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)


class Transaction(BaseModel):
    """The shape a row has to satisfy to be processed and reach the curated data layer."""

    model_config = ConfigDict(str_strip_whitespace=True)
    transaction_id: str = Field(min_length=1)
    transaction_date: date
    category: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    merchant: str = Field(min_length=1)


def _reason(error: ValidationError) -> str:
    """Cleans up Pydantic's returned error structure into one readable reason."""
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors())


def parse_csv(payload: str) -> list[dict]:
    """Parse raw CSV into dicts, no validation."""
    return list(csv.DictReader(io.StringIO(payload)))


def validate_rows(rows: list[dict]) -> tuple[list[Transaction], list[dict]]:
    """Split rows into accepted and rejected rows (with reasons) depending on the class validation

    Duplicate primary keys are detected across the batch by maintaining a set of seen ids. This
    means the first occurrence is accepted and later ones are quarantined, which makes the outcome
    depend on input order — that's acceptable because a transaction is an immutable event, so a
    repeated ID would be a defect to check.
    """
    accepted_rows: list[Transaction] = []
    rejected_rows: list[dict] = []
    previously_seen_ids: set[str] = set()

    for row in rows:
        try:
            # Unpacks dict into keyword arguments
            transaction = Transaction(**row)
        except ValidationError as error:
            # If row does not conform to Transaction shape, append to rejected with the formatted
            # pydantic reason and continue
            rejected_rows.append({**row, "reject_reason": _reason(error)})
            continue

        # If the id has already been seen, append to rejected with this reason and continue
        if transaction.transaction_id in previously_seen_ids:
            rejected_rows.append({**row, "reject_reason": "transaction_id: duplicate primary key"})
            continue

        # Otherwise add transaction_id to seen set
        previously_seen_ids.add(transaction.transaction_id)

        # Append all to accepted_rows
        accepted_rows.append(transaction)

    logger.info(
        "Validated %d rows: %d accepted, %d rejected",
        len(rows),
        len(accepted_rows),
        len(rejected_rows),
    )
    return accepted_rows, rejected_rows


def to_csv(rows: list[dict], fieldnames: list[str]) -> str:
    """Convert rows back to CSV, for writing to quarantine folder."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
