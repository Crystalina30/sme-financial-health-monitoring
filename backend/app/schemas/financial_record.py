"""Request and response schemas for financial records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.financial_inputs import FinancialInputs


class FinancialRecordCreateRequest(BaseModel):
    """Financial statement values submitted for one reporting period.

    Field-level rules (no negative revenue, no negative asset balances) are
    enforced here. Cross-field rules, including the accounting identity, are
    applied by the validation service once the fields themselves are sound.
    """

    reporting_period_id: int

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

    def to_financial_inputs(self) -> FinancialInputs:
        """Convert to the engine's input model."""
        return FinancialInputs(
            revenue=self.revenue,
            cost_of_goods_sold=self.cost_of_goods_sold,
            operating_expenses=self.operating_expenses,
            interest_expense=self.interest_expense,
            tax_expense=self.tax_expense,
            net_profit=self.net_profit,
            cash_and_equivalents=self.cash_and_equivalents,
            accounts_receivable=self.accounts_receivable,
            inventory=self.inventory,
            current_assets=self.current_assets,
            total_assets=self.total_assets,
            current_liabilities=self.current_liabilities,
            total_liabilities=self.total_liabilities,
            total_equity=self.total_equity,
        )


class FinancialRecordUpdateRequest(BaseModel):
    """A correction to a stored record, submitted as a complete replacement.

    Applying an update stores a new revision; the previous revision is kept so
    that historical assessments remain reproducible.
    """

    revenue: float = Field(ge=0)
    cost_of_goods_sold: float = Field(ge=0)
    operating_expenses: float = Field(ge=0)
    interest_expense: float = Field(default=0.0, ge=0)
    tax_expense: float = Field(default=0.0)
    net_profit: float
    cash_and_equivalents: float = Field(default=0.0, ge=0)
    accounts_receivable: float = Field(default=0.0, ge=0)
    inventory: float | None = Field(default=None, ge=0)
    current_assets: float = Field(ge=0)
    total_assets: float = Field(ge=0)
    current_liabilities: float = Field(ge=0)
    total_liabilities: float = Field(ge=0)
    total_equity: float

    def to_financial_inputs(self) -> FinancialInputs:
        return FinancialInputs(**self.model_dump())


class FinancialRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reporting_period_id: int
    revision: int
    is_current: bool
    revenue: float
    cost_of_goods_sold: float
    operating_expenses: float
    interest_expense: float
    tax_expense: float
    net_profit: float
    cash_and_equivalents: float
    accounts_receivable: float
    inventory: float | None
    current_assets: float
    total_assets: float
    current_liabilities: float
    total_liabilities: float
    total_equity: float
    accounting_identity_ok: bool
    validation_notes: str | None
    created_at: datetime
