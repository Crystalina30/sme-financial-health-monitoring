"""Financial statement fixtures used across the test suite.

Every fixture satisfies the accounting identity, so a test that is not about
validation is never tripped up by it.
"""

from app.schemas.financial_inputs import FinancialInputs

#: A company in sound financial health.
#:
#: Expected indicators, computed by hand:
#:   current ratio        300000 / 120000 = 2.50
#:   quick ratio          (300000 - 80000) / 120000 = 1.8333
#:   gross profit margin  (1000000 - 600000) / 1000000 = 40.0%
#:   net profit margin    120000 / 1000000 = 12.0%
#:   return on assets     120000 / 800000 = 15.0%
#:   debt to equity       300000 / 500000 = 0.60
#:   debt ratio           300000 / 800000 = 0.375
#:   interest coverage    (400000 - 220000) / 20000 = 9.0
#:   asset turnover       1000000 / 800000 = 1.25
#:   days sales out.      90000 / 1000000 * 365 = 32.85
SOUND_COMPANY = FinancialInputs(
    revenue=1_000_000,
    cost_of_goods_sold=600_000,
    operating_expenses=220_000,
    interest_expense=20_000,
    tax_expense=40_000,
    net_profit=120_000,
    cash_and_equivalents=130_000,
    accounts_receivable=90_000,
    inventory=80_000,
    current_assets=300_000,
    total_assets=800_000,
    current_liabilities=120_000,
    total_liabilities=300_000,
    total_equity=500_000,
)

#: A company in clear financial difficulty: thin liquidity, a loss, heavy
#: gearing and slow collection.
DISTRESSED_COMPANY = FinancialInputs(
    revenue=500_000,
    cost_of_goods_sold=440_000,
    operating_expenses=120_000,
    interest_expense=45_000,
    tax_expense=0,
    net_profit=-105_000,
    cash_and_equivalents=5_000,
    accounts_receivable=160_000,
    inventory=60_000,
    current_assets=225_000,
    total_assets=600_000,
    current_liabilities=300_000,
    total_liabilities=520_000,
    total_equity=80_000,
)

#: A service business that reports no inventory, so the quick ratio is not
#: applicable, and has no borrowings, so interest coverage is not applicable.
SERVICE_COMPANY_NO_INVENTORY = FinancialInputs(
    revenue=400_000,
    cost_of_goods_sold=150_000,
    operating_expenses=180_000,
    interest_expense=0,
    tax_expense=15_000,
    net_profit=55_000,
    cash_and_equivalents=90_000,
    accounts_receivable=40_000,
    inventory=None,
    current_assets=130_000,
    total_assets=250_000,
    current_liabilities=60_000,
    total_liabilities=90_000,
    total_equity=160_000,
)


def as_request_payload(data: FinancialInputs, reporting_period_id: int) -> dict:
    """Turn fixture inputs into a financial record creation payload."""
    payload = data.model_dump()
    payload["reporting_period_id"] = reporting_period_id
    return payload
