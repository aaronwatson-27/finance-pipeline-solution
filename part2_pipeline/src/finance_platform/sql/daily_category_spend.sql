-- Daily spend aggregates by category

SELECT
    transaction_date,
    category,
    COUNT(*)                AS transaction_count,
    ROUND(SUM(amount), 2)   AS total_spend,
    ROUND(AVG(amount), 2)   AS average_spend,
    ROUND(MIN(amount), 2)   AS min_spend,
    ROUND(MAX(amount), 2)   AS max_spend
FROM read_csv(
    $source_path,
    header = true,
    columns = {
        'transaction_id':   'VARCHAR',
        'transaction_date': 'DATE',
        'category':         'VARCHAR',
        'amount':           'DECIMAL(12,2)',
        'merchant':         'VARCHAR'
    }
)
GROUP BY transaction_date, category
ORDER BY transaction_date, category
