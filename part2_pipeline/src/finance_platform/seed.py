"""Create stable transaction-like data, including deliberate defects.

Uses a seed so the data is not random - required for the idempotency test.
This mocks real data we would normally ingest from an API or other source system.
"""

import csv
import io
import random
from datetime import date

MERCHANTS = {
    "Woolworths": ("groceries", 15.00, 220.00),
    "Coles": ("groceries", 15.00, 220.00),
    "IGA": ("groceries", 8.00, 90.00),
    "Market Lane Coffee": ("coffee beans", 4.50, 58.00),
    "Patricia Coffee Brewers": ("coffee beans", 4.50, 22.00),
    "Baker Bleu": ("bread", 7.00, 45.00),
    "Lune Croissants": ("pastries", 6.50, 38.00),
    "Dan Murphy's": ("alcohol", 20.00, 180.00),
}

MERCHANT_NAMES = sorted(MERCHANTS)

FIELDNAMES = ["transaction_id", "transaction_date", "category", "amount", "merchant"]


# Create valid transaction rows
def _transaction(run_date: date, index: int, rng: random.Random) -> dict:
    """Build valid transaction, with category and amount consistent with the merchant."""
    merchant = rng.choice(MERCHANT_NAMES)

    # Pick out correct category and min/max range for this merchant
    category, low, high = MERCHANTS[merchant]

    return {
        "transaction_id": f"TXN-{run_date:%Y%m%d}-{index:05d}",
        "transaction_date": run_date.isoformat(),
        "category": category,
        "amount": f"{rng.uniform(low, high):.2f}",
        "merchant": merchant,
    }


# Create purposely defective rows
def _defective_rows(run_date: date, first_valid: dict) -> list[dict]:
    """Five defects spanning both failure classes.

    Unparseable: missing ID, non-numeric amount, unparseable date.
    Parseable but invalid (based on business rules): negative amount, duplicate ID.
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
            "category": "coffee beans",
            "amount": "not_a_number",
            "merchant": "Market Lane Coffee",
        },
        {
            "transaction_id": f"TXN-{stamp}-90002",
            "transaction_date": "31/02/2026",
            "category": "pastries",
            "amount": "37.00",
            "merchant": "Lune Croissants",
        },
        {
            "transaction_id": f"TXN-{stamp}-90003",
            "transaction_date": run_date.isoformat(),
            "category": "bread",
            "amount": "-85.50",
            "merchant": "Baker Bleu",
        },
        dict(first_valid),
    ]


# Generate a csv from a mix of valid and invalid data
def generate_csv(run_date: date, row_count: int, random_seed: int) -> str:
    """Return a CSV string of transactions for run_date, defects included.

    Seeded RNG, so the same arguments always produce identical bytes.
    """
    rng = random.Random(random_seed)

    rows = [_transaction(run_date, i, rng) for i in range(row_count)]
    rows += _defective_rows(run_date, rows[0])

    # Scatter the defects through the file, so nothing can pass by relying on row ordering.
    # Uses the same seeded RNG, so ordering stays deterministic.
    rng.shuffle(rows)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


if __name__ == "__main__":
    import sys

    run_date = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    print(generate_csv(run_date, 10, 7))
