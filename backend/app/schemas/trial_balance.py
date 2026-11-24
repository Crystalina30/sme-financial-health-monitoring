"""Request and response schemas for trial balance input."""

from pydantic import BaseModel, ConfigDict, Field

from app.services.trial_balance_service import Derivation, Line

#: A generous upper bound; an SME trial balance is usually tens to a few
#: hundred rows.
MAX_LINES = 2000


class TrialBalanceLineIn(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    account_code: str = Field(default="", max_length=40)
    account_name: str = Field(min_length=1, max_length=200)
    account_group: str = Field(default="", max_length=120)
    debit: float = Field(default=0.0, ge=0)
    credit: float = Field(default=0.0, ge=0)
    category: str | None = Field(default=None, max_length=40)
    source_ref: str = Field(default="", max_length=200)


class TrialBalanceLinesRequest(BaseModel):
    lines: list[TrialBalanceLineIn] = Field(max_length=MAX_LINES)

    def to_lines(self) -> list[Line]:
        return [
            Line(
                line_number=index,
                account_code=line.account_code.strip(),
                account_name=line.account_name.strip(),
                debit=round(line.debit, 2),
                credit=round(line.credit, 2),
                category=line.category or None,
                account_group=line.account_group.strip(),
                source_ref=line.source_ref.strip(),
            )
            for index, line in enumerate(self.lines, start=1)
        ]


class TrialBalanceSubmitRequest(TrialBalanceLinesRequest):
    reporting_period_id: int


class CategoryResponse(BaseModel):
    code: str
    label: str
    statement: str
    normal_side: str
    examples: str


class ContributionResponse(BaseModel):
    line_number: int
    account_code: str
    account_name: str
    category: str
    amount: float
    source_ref: str = ""


class FigureResponse(BaseModel):
    value: float | None
    formula: str
    contributions: list[ContributionResponse]


class InventoryResponse(BaseModel):
    method: str
    label: str
    explanation: str
    needs_closing_stock: bool
    needs_review: bool = False
    opening_balance_in_inventory: float | None


class DerivationResponse(BaseModel):
    figures: dict[str, FigureResponse]
    category_totals: dict[str, float]
    total_debit: float
    total_credit: float
    difference: float
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    inventory: InventoryResponse | None = None

    @classmethod
    def from_derivation(cls, derivation: Derivation) -> "DerivationResponse":
        return cls(
            figures={
                name: FigureResponse(
                    value=figure.value,
                    formula=figure.formula,
                    contributions=[ContributionResponse(**vars(c)) for c in figure.contributions],
                )
                for name, figure in derivation.figures.items()
            },
            category_totals=derivation.category_totals,
            total_debit=derivation.total_debit,
            total_credit=derivation.total_credit,
            difference=derivation.difference,
            is_valid=derivation.is_valid,
            errors=derivation.errors,
            warnings=derivation.warnings,
            inventory=InventoryResponse(**vars(derivation.inventory))
            if derivation.inventory else None,
        )


class TrialBalanceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_number: int
    account_code: str
    account_name: str
    account_group: str
    debit: float
    credit: float
    category: str
    source_ref: str


class StoredTrialBalanceResponse(BaseModel):
    financial_record_id: int
    revision: int
    lines: list[TrialBalanceLineOut]
    derivation: DerivationResponse


class SuggestLineIn(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    account_code: str = Field(default="", max_length=40)
    account_name: str = Field(default="", max_length=200)
    account_group: str = Field(default="", max_length=120)
    debit: float = 0.0
    credit: float = 0.0


class SuggestRequest(BaseModel):
    lines: list[SuggestLineIn] = Field(max_length=MAX_LINES)


class Suggestion(BaseModel):
    category: str | None
    # "previous_period": the same account was categorised this way before for
    # this company; "account_group": from the group/type in the export;
    # "account_name": matched a keyword in the name; None: no suggestion,
    # the user must choose.
    basis: str | None


class SuggestResponse(BaseModel):
    suggestions: list[Suggestion]


class ImportedLineResponse(BaseModel):
    account_code: str
    account_name: str
    account_group: str
    debit: float
    credit: float
    category: str | None
    basis: str | None
    source_ref: str


class SheetImportResponse(BaseModel):
    name: str
    header_row: int | None
    columns: dict[str, str]
    lines: list[ImportedLineResponse]
    skipped_rows: list[int]
    total_debit: float
    total_credit: float
    errors: list[str]
    warnings: list[str]


class FileImportResponse(BaseModel):
    file_name: str
    file_type: str
    selected_sheet: str | None
    sheets: list[SheetImportResponse]
