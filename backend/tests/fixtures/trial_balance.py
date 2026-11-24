"""A sample pre-closing trial balance for an SME, in MYR.

It balances (debits = credits = 2,510,000) and includes contra accounts
(sales returns, closing stock, the allowance for doubtful debts and
accumulated depreciation), so the netting rules are exercised. The same rows
are published as docs/sample_trial_balance.csv for trying the import.

Expected figures:
    revenue 1,200,000; cost of goods sold 780,000; operating expenses 260,000;
    interest 30,000; tax 30,000; other income 2,000; net profit 102,000;
    cash 120,000; receivables 180,000; inventory 150,000;
    current assets 470,000; total assets 1,100,000;
    current liabilities 300,000; total liabilities 600,000;
    total equity 500,000; retained earnings 200,000.
"""

# (code, name, debit, credit, category)
SAMPLE_ROWS = [
    ("1000", "Maybank current account", 115_000, 0, "cash"),
    ("1010", "Petty cash", 5_000, 0, "cash"),
    ("1100", "Trade debtors", 190_000, 0, "accounts_receivable"),
    ("1110", "Allowance for doubtful debts", 0, 10_000, "accounts_receivable"),
    ("1200", "Stock", 150_000, 0, "inventory"),
    ("1300", "Prepayments", 20_000, 0, "other_current_asset"),
    ("1500", "Motor vehicles", 400_000, 0, "non_current_asset"),
    ("1510", "Office equipment", 330_000, 0, "non_current_asset"),
    ("1520", "Accumulated depreciation", 0, 100_000, "non_current_asset"),
    ("2000", "Trade creditors", 0, 240_000, "current_liability"),
    ("2010", "Accruals", 0, 30_000, "current_liability"),
    ("2020", "SST payable", 0, 30_000, "current_liability"),
    ("2500", "Term loan", 0, 300_000, "non_current_liability"),
    ("3000", "Share capital", 0, 300_000, "equity"),
    ("3100", "Retained earnings", 0, 98_000, "retained_earnings"),
    ("4000", "Sales", 0, 1_250_000, "revenue"),
    ("4010", "Sales returns", 50_000, 0, "revenue"),
    ("4900", "Interest received", 0, 2_000, "other_income"),
    ("5000", "Opening stock", 140_000, 0, "cost_of_sales"),
    ("5010", "Purchases", 760_000, 0, "cost_of_sales"),
    ("5020", "Carriage inwards", 30_000, 0, "cost_of_sales"),
    ("5090", "Closing stock", 0, 150_000, "cost_of_sales"),
    ("6000", "Salaries and wages", 150_000, 0, "operating_expense"),
    ("6010", "Rent", 60_000, 0, "operating_expense"),
    ("6020", "Utilities", 20_000, 0, "operating_expense"),
    ("6030", "Depreciation", 30_000, 0, "operating_expense"),
    ("7000", "Interest on term loan", 30_000, 0, "interest_expense"),
    ("8000", "Income tax", 30_000, 0, "tax_expense"),
]

EXPECTED = {
    "revenue": 1_200_000,
    "cost_of_goods_sold": 780_000,
    "operating_expenses": 260_000,
    "interest_expense": 30_000,
    "tax_expense": 30_000,
    "net_profit": 102_000,
    "cash_and_equivalents": 120_000,
    "accounts_receivable": 180_000,
    "inventory": 150_000,
    "current_assets": 470_000,
    "total_assets": 1_100_000,
    "current_liabilities": 300_000,
    "total_liabilities": 600_000,
    "total_equity": 500_000,
    "retained_earnings": 200_000,
}


def sample_payload(rows=SAMPLE_ROWS) -> list[dict]:
    return [
        {"account_code": code, "account_name": name, "debit": debit, "credit": credit,
         "category": category}
        for code, name, debit, credit, category in rows
    ]
