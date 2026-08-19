"""Quality gate tests."""

from decimal import Decimal

from finance_platform.quality import parse_csv, to_csv, validate_rows


def row(**overrides) -> dict:
    """A valid transaction row, with fields overridden per test."""
    return {
        "transaction_id": "TXN-20260818-00001",
        "transaction_date": "2026-08-18",
        "category": "cafe",
        "amount": "12.50",
        "merchant": "Market Lane Coffee",
        **overrides,
    }


# --- Happy path -----------------------------------------------------------


def test_valid_row_is_accepted():
    accepted, rejected = validate_rows([row()])

    assert len(accepted) == 1
    assert rejected == []
    assert accepted[0].amount == Decimal("12.50")


# --- Structural failures: the row cannot be interpreted -------------------


def test_missing_primary_key_is_rejected():
    accepted, rejected = validate_rows([row(transaction_id="")])

    assert accepted == []
    assert len(rejected) == 1
    assert "transaction_id" in rejected[0]["reject_reason"]


def test_non_numeric_amount_is_rejected():
    accepted, rejected = validate_rows([row(amount="not_a_number")])

    assert accepted == []
    assert "amount" in rejected[0]["reject_reason"]


def test_unparseable_date_is_rejected():
    accepted, rejected = validate_rows([row(transaction_date="31/02/2026")])

    assert accepted == []
    assert "transaction_date" in rejected[0]["reject_reason"]


# --- Business rule failures: the row parses but is invalid ----------------


def test_negative_amount_is_rejected():
    accepted, rejected = validate_rows([row(amount="-85.50")])

    assert accepted == []
    assert "amount" in rejected[0]["reject_reason"]


def test_zero_amount_is_rejected():
    """The rule is amount > 0, not amount >= 0."""
    accepted, rejected = validate_rows([row(amount="0.00")])

    assert accepted == []
    assert "amount" in rejected[0]["reject_reason"]


def test_duplicate_primary_key_is_rejected_keeping_the_first():
    accepted, rejected = validate_rows([row(amount="10.00"), row(amount="20.00")])

    assert len(accepted) == 1
    assert accepted[0].amount == Decimal("10.00")
    assert len(rejected) == 1
    assert "duplicate" in rejected[0]["reject_reason"]


# --- Quarantine behaviour ------------------------------------------------


def test_rejected_rows_retain_all_original_fields():
    """Quarantine must be replayable, so the full record is preserved — not just
    an error message. Anything dropped here is data lost."""
    bad = row(amount="-1.00", merchant="Dan Murphy's")
    _, rejected = validate_rows([bad])

    for field, value in bad.items():
        assert rejected[0][field] == value


def test_multiple_failures_are_all_reported():
    """One row with two problems yields one reject listing both, so a single
    pass through the data surfaces every issue."""
    _, rejected = validate_rows([row(transaction_id="", amount="-5.00")])

    reason = rejected[0]["reject_reason"]
    assert "transaction_id" in reason
    assert "amount" in reason


# --- Batch behaviour -----------------------------------------------------


def test_good_and_bad_rows_are_separated_in_one_pass():
    rows = [
        row(transaction_id="T1"),
        row(transaction_id="T2", amount="-1.00"),
        row(transaction_id="T3"),
        row(transaction_id=""),
    ]
    accepted, rejected = validate_rows(rows)

    assert [t.transaction_id for t in accepted] == ["T1", "T3"]
    assert len(rejected) == 2


def test_empty_input_is_handled():
    assert validate_rows([]) == ([], [])


# --- Round trip through CSV ---------------------------------------------


def test_parse_and_validate_from_raw_csv():
    """The gate consumes what the landing layer stores: raw CSV text."""
    csv_text = (
        "transaction_id,transaction_date,category,amount,merchant\n"
        "T1,2026-08-18,cafe,12.50,Market Lane Coffee\n"
        "T2,2026-08-18,cafe,-3.00,Market Lane Coffee\n"
    )
    accepted, rejected = validate_rows(parse_csv(csv_text))

    assert len(accepted) == 1
    assert len(rejected) == 1


def test_quarantine_csv_includes_the_reason_column():
    _, rejected = validate_rows([row(amount="-1.00")])
    fieldnames = [*row().keys(), "reject_reason"]

    output = to_csv(rejected, fieldnames)

    assert output.splitlines()[0].endswith("reject_reason")
    assert "amount:" in output
