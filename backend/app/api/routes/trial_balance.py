"""Trial balance routes.

These accept the raw account balances an accountant exports from the ledger,
calculate the statement figures from them, and store both, so every figure on
the dashboard can be traced back to the accounts it came from.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    company_for_member,
    get_current_user,
    get_owned_company,
    get_owned_period,
)
from app.api.routes.financial_records import _apply_values
from app.core.database import get_db
from app.models.company import Company, ReportingPeriod
from app.models.financial_record import FinancialRecord
from app.models.trial_balance import TrialBalanceLine
from app.models.user import User
from app.schemas.financial_record import FinancialRecordResponse, FinancialRecordUpdateRequest
from app.schemas.trial_balance import (
    CategoryResponse,
    DerivationResponse,
    FileImportResponse,
    ImportedLineResponse,
    SheetImportResponse,
    StoredTrialBalanceResponse,
    SuggestRequest,
    SuggestResponse,
    Suggestion,
    TrialBalanceLineOut,
    TrialBalanceLinesRequest,
    TrialBalanceSubmitRequest,
)
from app.services.trial_balance_import import (
    MAX_FILE_BYTES,
    ImportFileError,
    import_trial_balance_file,
)
from app.services.trial_balance_service import CATEGORIES, Line, derive, suggest
from app.services.validation_service import validate_financial_inputs
from app.services.audit_service import record_event
from app.utils.records import commit_revision, get_current_record, lock_period

router = APIRouter(tags=["trial balance"])


def _unprocessable(errors: list[str]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"message": "The trial balance could not be used.", "errors": errors},
    )


@router.get(
    "/trial-balance/categories",
    response_model=list[CategoryResponse],
    summary="List the account categories",
)
def list_categories(_: User = Depends(get_current_user)) -> list[CategoryResponse]:
    return [CategoryResponse(**vars(category)) for category in CATEGORIES]


@router.post(
    "/trial-balance/preview",
    response_model=DerivationResponse,
    summary="Calculate statement figures from a trial balance without saving",
)
def preview_trial_balance(
    payload: TrialBalanceLinesRequest, _: User = Depends(get_current_user)
) -> DerivationResponse:
    return DerivationResponse.from_derivation(derive(payload.to_lines()))


@router.post(
    "/companies/{company_id}/trial-balance/suggest",
    response_model=SuggestResponse,
    summary="Suggest a category for each account",
)
def suggest_categories(
    payload: SuggestRequest,
    company: Company = Depends(get_owned_company),
    db: Session = Depends(get_db),
) -> SuggestResponse:
    """Suggest categories, preferring what this company used before.

    An account the company has categorised in an earlier trial balance gets
    the same category again (matched by code, or by name when there is no
    code). Otherwise the group in the export, then the account name, are
    used. The user confirms every category before anything is calculated.
    """
    return SuggestResponse(suggestions=_suggest_for(db, company, payload.lines))


def _suggest_for(db: Session, company: Company, lines) -> list[Suggestion]:
    previous = db.execute(
        select(TrialBalanceLine.account_code, TrialBalanceLine.account_name,
               TrialBalanceLine.category)
        .join(FinancialRecord)
        .join(ReportingPeriod)
        .where(ReportingPeriod.company_id == company.id)
        .order_by(FinancialRecord.id.desc(), TrialBalanceLine.line_number)
    ).all()
    by_code: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for code, name, category in previous:  # newest record first, so first seen wins
        if code:
            by_code.setdefault(code.strip().lower(), category)
        by_name.setdefault(name.strip().lower(), category)

    suggestions = []
    for line in lines:
        code = line.account_code.strip().lower()
        name = line.account_name.strip().lower()
        remembered = by_code.get(code) if code else by_name.get(name)
        if remembered:
            suggestions.append(Suggestion(category=remembered, basis="previous_period"))
            continue
        category, basis = suggest(line.account_name, line.account_group, line.debit, line.credit)
        suggestions.append(Suggestion(category=category, basis=basis))
    return suggestions


@router.post(
    "/companies/{company_id}/trial-balance/import",
    response_model=FileImportResponse,
    summary="Read a trial balance from an Excel or CSV file",
)
async def import_trial_balance(
    file: UploadFile = File(...),
    company: Company = Depends(get_owned_company),
    db: Session = Depends(get_db),
) -> FileImportResponse:
    """Read the trial balance table(s) in an uploaded file, without saving.

    Every worksheet is examined; the response lists each table found and the
    one judged most likely to be the trial balance. Each line carries a
    suggested category and a reference to its source row. Nothing is stored
    until the user has reviewed the categories and submits the trial balance.
    """
    data = await file.read(MAX_FILE_BYTES + 1)
    lookup = {}
    for category in CATEGORIES:
        lookup[category.code] = category.code
        lookup[category.label.lower()] = category.code
    try:
        result = import_trial_balance_file(file.filename or "upload", data, lookup)
    except ImportFileError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    sheets = []
    for sheet in result.sheets:
        suggestions = _suggest_for(db, company, sheet.lines)
        sheets.append(
            SheetImportResponse(
                name=sheet.name,
                header_row=sheet.header_row,
                columns=sheet.columns,
                lines=[
                    ImportedLineResponse(
                        account_code=line.account_code,
                        account_name=line.account_name,
                        account_group=line.account_group,
                        debit=line.debit,
                        credit=line.credit,
                        category=line.category or suggestion.category,
                        basis="file" if line.category else suggestion.basis,
                        source_ref=line.source_ref,
                    )
                    for line, suggestion in zip(sheet.lines, suggestions)
                ],
                skipped_rows=sheet.skipped_rows,
                total_debit=sheet.total_debit,
                total_credit=sheet.total_credit,
                errors=sheet.errors,
                warnings=sheet.warnings,
            )
        )
    return FileImportResponse(
        file_name=result.file_name,
        file_type=result.file_type,
        selected_sheet=result.selected_sheet,
        sheets=sheets,
    )


@router.post(
    "/companies/{company_id}/trial-balance",
    response_model=FinancialRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store a trial balance and the figures calculated from it",
)
def submit_trial_balance(
    payload: TrialBalanceSubmitRequest,
    company: Company = Depends(get_owned_company),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FinancialRecord:
    """Calculate the statement figures and store them with the trial balance.

    If the period already has a record, the result is stored as a new
    revision and the earlier one is kept, as with any correction.
    """
    period = get_owned_period(db, company, payload.reporting_period_id)
    lines = payload.to_lines()
    derivation = derive(lines)
    if not derivation.is_valid:
        raise _unprocessable(derivation.errors)

    try:
        figures = FinancialRecordUpdateRequest(**derivation.record_values())
    except ValidationError as exc:  # pragma: no cover - derive() already checks signs
        raise _unprocessable([error["msg"] for error in exc.errors()]) from exc

    validation = validate_financial_inputs(figures.to_financial_inputs())
    if not validation.is_valid:
        raise _unprocessable(validation.errors)

    lock_period(db, period.id)
    current = get_current_record(db, period.id)
    if current is not None:
        current.is_current = False
    record = FinancialRecord(
        reporting_period_id=period.id,
        revision=current.revision + 1 if current else 1,
        is_current=True,
        source="trial_balance",
        created_by_user_id=current_user.id,
        accounting_identity_ok=validation.accounting_identity_ok,
        validation_notes=validation.notes,
    )
    _apply_values(record, figures)
    record.trial_balance_lines = [
        TrialBalanceLine(
            line_number=line.line_number,
            account_code=line.account_code,
            account_name=line.account_name,
            debit=line.debit,
            credit=line.credit,
            category=line.category,
            account_group=line.account_group,
            source_ref=line.source_ref,
        )
        for line in lines
    ]
    db.add(record)
    db.flush()
    record_event(
        db, company_id=company.id, actor=current_user, action="trial_balance.imported",
        entity_type="financial_record", entity_id=record.id,
        detail={
            "period": period.label,
            "revision": record.revision,
            "lines": len(lines),
            "inventory_method": derivation.inventory.method if derivation.inventory else None,
            # Stock counts and confirmations entered in the app, kept as evidence.
            "period_end_adjustments": [
                {"account": line.account_name, "debit": line.debit, "credit": line.credit,
                 "note": line.source_ref}
                for line in lines if line.source_ref.startswith("Period-end adjustment")
            ],
        },
    )
    commit_revision(db)
    db.refresh(record)
    return record


@router.get(
    "/financial-records/{record_id}/trial-balance",
    response_model=StoredTrialBalanceResponse,
    summary="The trial balance behind a financial record",
)
def get_trial_balance(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoredTrialBalanceResponse:
    record = db.get(FinancialRecord, record_id)
    period = db.get(ReportingPeriod, record.reporting_period_id) if record else None
    try:
        if period is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        company_for_member(db, current_user, period.company_id)
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Financial record not found."
        ) from exc
    if record.source != "trial_balance":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This record was entered as statement totals and has no trial balance.",
        )

    stored = [
        Line(row.line_number, row.account_code, row.account_name,
             float(row.debit), float(row.credit), row.category,
             row.account_group, row.source_ref)
        for row in record.trial_balance_lines
    ]
    return StoredTrialBalanceResponse(
        financial_record_id=record.id,
        revision=record.revision,
        lines=[TrialBalanceLineOut.model_validate(row) for row in record.trial_balance_lines],
        derivation=DerivationResponse.from_derivation(derive(stored)),
    )
