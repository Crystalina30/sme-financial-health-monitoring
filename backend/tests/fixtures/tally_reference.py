"""Reference trial balance from an external accounting dataset.

Source: the "Tally ERP FY2017-18 Accounting College Project" dataset (a
student project on GitHub), workbook Financial_Statements_FY2017-18.xlsx,
sheet "Trial Balance", rows 2-18, for the fictitious company "Aarav Foods
Private Limited", 1 April 2017 to 31 March 2018, in INR.

The rows are copied exactly as published, so the tests do not depend on the
workbook being present. The dataset is synthetic and is NOT audited; see
ACCOUNTING_DATASET_VALIDATION.md for the problems found in it. It is used
here only to check that this system reproduces the arithmetic of a published
trial balance and its statements, not as evidence about any real company.

REFERENCE_STATEMENTS holds the results of the workbook's own Trading
Account, Profit & Loss and Balance Sheet formulas (their saved values).
"""

# (ledger, Tally group, debit, credit)
TALLY_TRIAL_BALANCE = [
    ("Cash & Bank", "Bank Accounts", 3580064.53, 0),
    ("Accounts Receivable", "Sundry Debtors", 0, 0),
    ("Inventory (Closing)", "Stock-in-Hand", 0, 0),
    ("Input CGST", "Duties & Taxes", 11887.17, 0),
    ("Input SGST", "Duties & Taxes", 11887.17, 0),
    ("Input IGST", "Duties & Taxes", 172840.14, 0),
    ("Accounts Payable", "Sundry Creditors", 0, 0),
    ("Output CGST", "Duties & Taxes", 0, 32481.91),
    ("Output SGST", "Duties & Taxes", 0, 32481.91),
    ("Output IGST", "Duties & Taxes", 0, 273881.74),
    ("Sales Revenue (Net of GST)", "Sales Accounts", 0, 2430335.31),
    ("Opening Stock", "Direct Expenses", 491290.86, 0),
    ("Purchases (Taxable Portion)", "Purchase Accounts", 1460006.65, 0),
    ("Freight Inward", "Direct Expenses", 31810.22, 0),
    ("Round Off (Purchases)", "Direct Expenses", 3.5, 0),
    ("Transportation Charges", "Indirect Expenses", 498841.1, 0),
    ("Capital Account", "Capital", 0, 3489450.47),
]

#: The category a bookkeeper would give each ledger, from its Tally group.
EXPECTED_CATEGORIES = {
    "Cash & Bank": "cash",
    "Accounts Receivable": "accounts_receivable",
    "Inventory (Closing)": "inventory",
    "Input CGST": "other_current_asset",
    "Input SGST": "other_current_asset",
    "Input IGST": "other_current_asset",
    "Accounts Payable": "current_liability",
    "Output CGST": "current_liability",
    "Output SGST": "current_liability",
    "Output IGST": "current_liability",
    "Sales Revenue (Net of GST)": "revenue",
    "Opening Stock": "cost_of_sales",
    "Purchases (Taxable Portion)": "cost_of_sales",
    "Freight Inward": "cost_of_sales",
    "Round Off (Purchases)": "cost_of_sales",
    "Transportation Charges": "operating_expense",
    "Capital Account": "equity",
}

#: Saved results of the reference workbook's statement formulas.
REFERENCE_STATEMENTS = {
    "revenue": 2430335.31,  # Profit & Loss!B3
    "cost_of_goods_sold": 1983111.23,  # Trading Account!B9
    "gross_profit": 447224.08,  # Profit & Loss!B5
    "operating_expenses": 498841.10,  # Profit & Loss!B9
    "net_profit": -51617.02,  # Profit & Loss!B11
    "cash_and_equivalents": 3580064.53,  # Balance Sheet!B4
    "accounts_receivable": 0.0,  # Balance Sheet!B5
    "inventory": 0.0,  # Balance Sheet!B6
    "total_assets": 3776679.01,  # Balance Sheet!B10
    # Balance Sheet!E4:E7 (payables and output GST)
    "current_liabilities": 338845.56,
    "total_liabilities": 338845.56,
    # Balance Sheet!E8 + E9 (capital + the year's profit)
    "total_equity": 3437833.45,
    "total_debit": 6258631.34,  # Trial Balance!C19
    "total_credit": 6258631.34,  # Trial Balance!D19
}

PERIOD_START = "2017-04-01"
PERIOD_END = "2018-03-31"
