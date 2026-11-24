"""Input model for the calculation engine.

This model is deliberately independent of the ORM. The engine accepts a plain
``FinancialInputs`` object, never a database row, so that the same engine can
be fed either a stored financial record or a projected position produced by
the FYP2 simulation layer without any change to the engine itself.
"""

from pydantic import BaseModel, ConfigDict, Field

#: Length of a reporting year, used to annualise flow-based ratios.
DAYS_IN_YEAR = 365


class FinancialInputs(BaseModel):
    """Standardised financial statement values required by the indicators.

    All monetary values are in the company's reporting currency and refer to
    the same reporting period. ``inventory`` is optional because some SMEs
    (service businesses in particular) do not report it; indicators that
    require it are reported as not applicable rather than as zero.
    ``retained_earnings`` is optional because it is used only by the separate
    Altman Z'' benchmark, never by the health score.
    """

    # Infinity and NaN are not amounts: they are refused at the boundary.
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    # ---- Income statement ------------------------------------------------
    revenue: float = Field(ge=0)
    cost_of_goods_sold: float = Field(ge=0)
    operating_expenses: float = Field(ge=0)
    interest_expense: float = Field(default=0.0, ge=0)
    tax_expense: float = Field(default=0.0)
    net_profit: float
    # Optional lines that reconcile operating profit to net profit. Each is
    # entered as a positive amount; zero when the statement has no such line.
    # They are defined so that nothing can be counted twice:
    #   other_operating_income  income from the business's own operations that
    #                           is not revenue (e.g. rental of spare premises,
    #                           government wage subsidies). Part of operating
    #                           profit.
    #   other_income            non-operating income: interest and dividends
    #                           received, gains on disposal of assets.
    #   other_expenses          non-operating expenses and losses: losses on
    #                           disposal, impairment losses, exchange losses.
    # Finance costs are interest_expense; a tax credit is a negative
    # tax_expense.
    other_operating_income: float = Field(default=0.0, ge=0)
    other_income: float = Field(default=0.0, ge=0)
    other_expenses: float = Field(default=0.0, ge=0)

    # ---- Balance sheet ---------------------------------------------------
    cash_and_equivalents: float = Field(default=0.0, ge=0)
    accounts_receivable: float = Field(default=0.0, ge=0)
    inventory: float | None = Field(default=None, ge=0)
    current_assets: float = Field(ge=0)
    total_assets: float = Field(ge=0)
    current_liabilities: float = Field(ge=0)
    total_liabilities: float = Field(ge=0)
    total_equity: float
    # Accumulated profits less losses and dividends; negative after
    # accumulated losses. None means not reported, never zero.
    retained_earnings: float | None = None

    # ---- Reporting period ------------------------------------------------
    # Length of the period the income-statement figures cover, in days. None
    # means unknown, in which case a full year is assumed and flagged.
    period_days: int | None = Field(default=None, ge=1)

    @property
    def gross_profit(self) -> float:
        """Revenue less cost of goods sold."""
        return self.revenue - self.cost_of_goods_sold

    @property
    def operating_profit(self) -> float:
        """Operating profit (EBIT): gross profit plus other operating income,
        less operating expenses. With no other operating income recorded this
        is gross profit less operating expenses, as before."""
        return self.gross_profit + self.other_operating_income - self.operating_expenses

    @property
    def profit_before_tax(self) -> float:
        """Operating profit plus non-operating income, less non-operating
        expenses and finance costs (interest)."""
        return (
            self.operating_profit + self.other_income - self.other_expenses
            - self.interest_expense
        )

    @property
    def effective_period_days(self) -> int:
        """Days the flow figures cover, assuming a full year when unknown."""
        return self.period_days if self.period_days is not None else DAYS_IN_YEAR
