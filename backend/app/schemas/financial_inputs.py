"""Input model for the calculation engine.

This model is deliberately independent of the ORM. The engine accepts a plain
``FinancialInputs`` object, never a database row, so that the same engine can
be fed either a stored financial record or a projected position produced by
the FYP2 simulation layer without any change to the engine itself.
"""

from pydantic import BaseModel, ConfigDict, Field


class FinancialInputs(BaseModel):
    """Standardised financial statement values required by the ten indicators.

    All monetary values are in the company's reporting currency and refer to
    the same reporting period. ``inventory`` is optional because some SMEs
    (service businesses in particular) do not report it; indicators that
    require it are reported as not applicable rather than as zero.
    """

    model_config = ConfigDict(frozen=True)

    # ---- Income statement ------------------------------------------------
    revenue: float = Field(ge=0)
    cost_of_goods_sold: float = Field(ge=0)
    operating_expenses: float = Field(ge=0)
    interest_expense: float = Field(default=0.0, ge=0)
    tax_expense: float = Field(default=0.0)
    net_profit: float

    # ---- Balance sheet ---------------------------------------------------
    cash_and_equivalents: float = Field(default=0.0, ge=0)
    accounts_receivable: float = Field(default=0.0, ge=0)
    inventory: float | None = Field(default=None, ge=0)
    current_assets: float = Field(ge=0)
    total_assets: float = Field(ge=0)
    current_liabilities: float = Field(ge=0)
    total_liabilities: float = Field(ge=0)
    total_equity: float

    @property
    def gross_profit(self) -> float:
        """Revenue less cost of goods sold."""
        return self.revenue - self.cost_of_goods_sold

    @property
    def operating_profit(self) -> float:
        """Gross profit less operating expenses (EBIT)."""
        return self.gross_profit - self.operating_expenses
