"""Create stable transaction-like data, including deliberate defects.

Uses a seed so the data is not random - required for the idempotency test.
This mocks real data we would normally ingest from an API or other source system.
"""

import csv
import io
import random
from datetime import date

CATEGORIES = ["groceries", "cafe", "restaurant", "takeaway", "bakery", "alcohol"]

MERCHANTS = [
    "Woolworths",
    "Coles",
    "IGA",
    "Market Lane Coffee",
    "Patricia Coffee Brewers",
    "Baker Bleu",
    "Lune Croissants",
    "Chin Chin",
    "Uber Eats",
    "Dan Murphy's",
]

FIELDNAMES = ["transaction_id", "transaction_date", "category", "amount", "merchant"]


def _defective_rows(run_date: date, first_valid: dict) -> list[dict]:
    """Simulates five defects of which failure classes can be a) unparseable (structural):
    missing ID, non-numeric amount, unparseable date, or b) Parseable but invalid (business rule):
    negative amount, duplicate ID.
    """
    stamp = f"{run_date:%Y%m%d}"
    return [
        {
            "transaction_id": "",
            "transaction_date": run_date.isoformat(),
            "category": "groceries",
            "amount": "42.00",
            "merchant": "Coles",
        },
        {
            "transaction_id": f"TXN-{stamp}-90001",
            "transaction_date": run_date.isoformat(),
            "category": "cafe",
            "amount": "not_a_number",
            "merchant": "Market Lane Coffee",
        },
        {
            "transaction_id": f"TXN-{stamp}-90002",
            "transaction_date": "31/02/2026",
            "category": "restaurant",
            "amount": "199.00",
            "merchant": "Chin Chin",
        },
        {
            "transaction_id": f"TXN-{stamp}-90003",
            "transaction_date": run_date.isoformat(),
            "category": "bakery",
            "amount": "-85.50",
            "merchant": "Baker Bleu",
        },
        dict(first_valid),
    ]


def generate_csv(run_date: date, row_count: int, random_seed: int) -> str:
    """Return a CSV string of transactions for run_date, defects included.

    Seeded RNG, so the same arguments always produce identical bytes.
    """
    rng = random.Random(random_seed)

    rows = [
        {
            "transaction_id": f"TXN-{run_date:%Y%m%d}-{i:05d}",
            "transaction_date": run_date.isoformat(),
            "category": rng.choice(CATEGORIES),
            "amount": f"{rng.uniform(5.0, 250.0):.2f}",
            "merchant": rng.choice(MERCHANTS),
        }
        for i in range(row_count)
    ]

    rows += _defective_rows(run_date, rows[0])

    # Shuffle the defects into the file, as they would be in a real feed, so
    # nothing downstream can pass because the ordering just happened to work out. Uses the same
    # seeded RNG, so ordering stays deterministic.
    rng.shuffle(rows)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


if __name__ == "__main__":
    import sys

    run_date = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    print(generate_csv(run_date, 5, 42))
