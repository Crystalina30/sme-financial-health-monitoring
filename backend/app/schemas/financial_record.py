"""Request and response schemas for financial records."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.financial_inputs import FinancialInputs


class FinancialRecordCreateRequest(BaseModel):
    """Financial statement values submitted for one reporting period.

    Field-level rules (no negative revenue, no negative asset balances) are
    enforced here. Cross-field rules, including the accounting identity, are
    applied by the validation service once the fields themselves are sound.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    reporting_period_id: int

    # ---- Income statement ------------------------------------------------
    revenue: float = Field(ge=0)
    cost_of_goods_sold: float = Field(ge=0)
    operating_expenses: float = Field(ge=0)
    interest_expense: float = Field(default=0.0, ge=0)
    tax_expense: float = Field(default=0.0)
    net_profit: float
    # Optional lines between operating profit and net profit; see
    # FinancialInputs for their exact definitions.
    other_operating_income: float = Field(default=0.0, ge=0)
    other_income: float = Field(default=0.0, ge=0)
    other_expenses: float = Field(default=0.0, ge=0)
    # Precision of the source figures: 0.01 (exact), 1, 1000 (RM'000) or
    # 1000000 (RM million). Amounts are always entered in full ringgit.
    presentation_unit: Literal[0.01, 1, 1000, 1000000] = 0.01

    # ---- Balance sheet ---------------------------------------------------
    cash_and_equivalents: float = Field(default=0.0, ge=0)
    accounts_receivable: float = Field(default=0.0, ge=0)
    inventory: float | None = Field(default=None, ge=0)
    current_assets: float = Field(ge=0)
    total_assets: float = Field(ge=0)
    current_liabilities: float = Field(ge=0)
    total_liabilities: float = Field(ge=0)
    total_equity: float
    # Used only by the Altman Z'' benchmark; negative after accumulated losses.
    retained_earnings: float | None = None

    def to_financial_inputs(self) -> FinancialInputs:
        """Convert to the engine's input model."""
        return FinancialInputs(
            revenue=self.revenue,
            cost_of_goods_sold=self.cost_of_goods_sold,
            operating_expenses=self.operating_expenses,
            interest_expense=self.interest_expense,
            tax_expense=self.tax_expense,
            net_profit=self.net_profit,
            other_operating_income=self.other_operating_income,
            other_income=self.other_income,
            other_expenses=self.other_expenses,
            cash_and_equivalents=self.cash_and_equivalents,
            accounts_receivable=self.accounts_receivable,
            inventory=self.inventory,
            current_assets=self.current_assets,
            total_assets=self.total_assets,
            current_liabilities=self.current_liabilities,
            total_liabilities=self.total_liabilities,
            total_equity=self.total_equity,
            retained_earnings=self.retained_earnings,
        )


class FinancialRecordUpdateRequest(BaseModel):
    """A correction to a stored record, submitted as a complete replacement.

    Applying an update stores a new revision; the previous revision is kept so
    that historical assessments remain reproducible.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    revenue: float = Field(ge=0)
    cost_of_goods_sold: float = Field(ge=0)
    operating_expenses: float = Field(ge=0)
    interest_expense: float = Field(default=0.0, ge=0)
    tax_expense: float = Field(default=0.0)
    net_profit: float
    # Optional lines between operating profit and net profit; see
    # FinancialInputs for their exact definitions.
    other_operating_income: float = Field(default=0.0, ge=0)
    other_income: float = Field(default=0.0, ge=0)
    other_expenses: float = Field(default=0.0, ge=0)
    # Precision of the source figures: 0.01 (exact), 1, 1000 (RM'000) or
    # 1000000 (RM million). Amounts are always entered in full ringgit.
    presentation_unit: Literal[0.01, 1, 1000, 1000000] = 0.01
    cash_and_equivalents: float = Field(default=0.0, ge=0)
    accounts_receivable: float = Field(default=0.0, ge=0)
    inventory: float | None = Field(default=None, ge=0)
    current_assets: float = Field(ge=0)
    total_assets: float = Field(ge=0)
    current_liabilities: float = Field(ge=0)
    total_liabilities: float = Field(ge=0)
    total_equity: float
    # Used only by the Altman Z'' benchmark; negative after accumulated losses.
    retained_earnings: float | None = None

    def to_financial_inputs(self) -> FinancialInputs:
        return FinancialInputs(**self.model_dump(exclude={"presentation_unit"}))


class FinancialRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reporting_period_id: int
    revision: int
    is_current: bool
    source: str
    revenue: float
    cost_of_goods_sold: float
    operating_expenses: float
    interest_expense: float
    tax_expense: float
    net_profit: float
    other_operating_income: float
    other_income: float
    other_expenses: float
    presentation_unit: float
    cash_and_equivalents: float
    accounts_receivable: float
    inventory: float | None
    current_assets: float
    total_assets: float
    current_liabilities: float
    total_liabilities: float
    total_equity: float
    retained_earnings: float | None
    accounting_identity_ok: bool
    validation_notes: str | None
    created_at: datetime
    created_by_email: str | None = None
