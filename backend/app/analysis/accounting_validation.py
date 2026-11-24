"""Validate the trial balance pipeline against an external accounting dataset.

Run from the backend folder:

    python -m app.analysis.accounting_validation \
        --statements PATH/Financial_Statements_FY2017-18.xlsx \
        --dataset PATH/Tally_ERP9_FY2017-18_Project_Dataset.xlsx \
        --output-dir ../docs/analysis

The reference trial balance is read through the product's own code: the
file importer, the category suggestions (no manual corrections), the
statement derivation, the indicator engine and the scoring engine. The
results are compared with:

1. the reference statements in the same workbook (their saved formula
   results, read with ``data_only``), and
2. independent hand formulas for every ratio and score, written here
   without calling the engine.

The voucher-level dataset is then reconciled with the reference trial
balance, to test the dataset itself. That part is specific to this dataset
(its sheet and column names) and is evidence for the report, not product
code. Nothing in the input files is modified.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from app.analysis.sensitivity import _default_thresholds
from app.schemas.financial_inputs import FinancialInputs
from app.services.benchmark_service import calculate_altman_z_double_prime
from app.services.financial_calculation_service import calculate_indicators
from app.services.scoring_service import assess, reference_points_for
from app.services.trial_balance_import import import_trial_balance_file
from app.services.trial_balance_service import CATEGORY_BY_CODE, Line, derive, suggest
from app.services.validation_service import validate_financial_inputs

#: Amounts are compared to the cent.
TOLERANCE = 0.01
PERIOD_START = date(2017, 4, 1)
PERIOD_END = date(2018, 3, 31)


def _load(path: Path, data_only: bool = True):
    import openpyxl

    return openpyxl.load_workbook(path, data_only=data_only)


# ---------------------------------------------------------------------------
# 1. The product pipeline on the reference trial balance
# ---------------------------------------------------------------------------


def run_pipeline(statements: Path) -> dict:
    result = import_trial_balance_file(statements.name, statements.read_bytes())
    sheet = next(s for s in result.sheets if s.name == result.selected_sheet)
    lines = []
    classification = []
    for number, imported in enumerate(sheet.lines, start=1):
        category, basis = suggest(
            imported.account_name, imported.account_group, imported.debit, imported.credit
        )
        lines.append(
            Line(number, imported.account_code, imported.account_name, imported.debit,
                 imported.credit, category, imported.account_group, imported.source_ref)
        )
        classification.append({
            "row": imported.source_ref.split("› ")[-1],
            "ledger": imported.account_name,
            "group": imported.account_group,
            "debit": imported.debit,
            "credit": imported.credit,
            "category": CATEGORY_BY_CODE[category].label if category else None,
            "basis": basis,
        })
    derivation = derive(lines)
    return {
        "file": result.file_name,
        "selected_sheet": result.selected_sheet,
        "sheets_examined": [
            {"name": s.name, "table_found": s.header_row is not None, "rows": len(s.lines)}
            for s in result.sheets
        ],
        "header_row": sheet.header_row,
        "columns": sheet.columns,
        "skipped_rows": sheet.skipped_rows,
        "import_errors": sheet.errors,
        "import_warnings": sheet.warnings,
        "classification": classification,
        "derivation": derivation,
    }


# ---------------------------------------------------------------------------
# 2. Reference statements
# ---------------------------------------------------------------------------


def _labelled_values(ws) -> dict[str, float]:
    """Label -> value for two-column statements (and the right-hand pair)."""
    out: dict[str, float] = {}
    for row in ws.iter_rows(values_only=True):
        for label_col, value_col in ((0, 1), (3, 4)):
            if len(row) > value_col and isinstance(row[label_col], str) and isinstance(
                row[value_col], (int, float)
            ):
                out[row[label_col].strip()] = float(row[value_col])
    return out


def reference_values(statements: Path) -> dict[str, float | None]:
    wb = _load(statements)
    trading = _labelled_values(wb["Trading Account"])
    pl = _labelled_values(wb["Profit & Loss"])
    bs = _labelled_values(wb["Balance Sheet"])
    current_liabilities = sum(
        bs[k] for k in ("Accounts Payable", "Output CGST", "Output SGST", "Output IGST")
    )
    equity = bs["Capital Account"] + bs["Retained Earnings (Net Profit)"]
    return {
        "revenue": pl["Net Sales (excl. GST)"],
        "cost_of_goods_sold": trading["COGS"],
        "gross_profit": pl["Gross Profit"],
        "operating_expenses": pl["Total Operating Expenses"],
        "operating_profit": pl["Gross Profit"] - pl["Total Operating Expenses"],
        "interest_expense": None,  # not presented in the reference statements
        "tax_expense": None,
        "net_profit": pl["Net Profit"],
        "cash_and_equivalents": bs["Cash & Bank"],
        "accounts_receivable": bs["Accounts Receivable"],
        "inventory": bs["Inventory"],
        "other_current_assets": bs["Input CGST"] + bs["Input SGST"] + bs["Input IGST"],
        "current_assets": bs["Total Assets"],  # every asset presented is current
        "non_current_assets": None,
        "total_assets": bs["Total Assets"],
        "current_liabilities": current_liabilities,
        "non_current_liabilities": None,
        "total_liabilities": current_liabilities,
        "total_equity": equity,
        "retained_earnings": None,  # the reference labels the year's profit only
        "total_liabilities_and_equity": bs["Total Liabilities & Equity"],
    }


FIGURE_LABELS = {
    "revenue": "Revenue", "cost_of_goods_sold": "Cost of goods sold",
    "gross_profit": "Gross profit", "operating_expenses": "Operating expenses",
    "operating_profit": "Operating profit", "interest_expense": "Interest expense",
    "tax_expense": "Tax expense", "net_profit": "Net profit",
    "cash_and_equivalents": "Cash and cash equivalents",
    "accounts_receivable": "Accounts receivable", "inventory": "Inventory",
    "other_current_assets": "Other current assets (input GST)",
    "current_assets": "Current assets", "non_current_assets": "Non-current assets",
    "total_assets": "Total assets", "current_liabilities": "Current liabilities",
    "non_current_liabilities": "Non-current liabilities",
    "total_liabilities": "Total liabilities", "total_equity": "Total equity",
    "retained_earnings": "Retained earnings",
}


def compare(derivation, reference: dict) -> list[dict]:
    rows = []
    for key, label in FIGURE_LABELS.items():
        ours = derivation.figures[key].value
        ref = reference.get(key)
        if ref is None:
            result = "Not in reference"
            difference = None
        elif ours is None:
            result = "Fail"
            difference = None
        else:
            difference = round(ours - ref, 2)
            result = "Pass" if abs(difference) <= TOLERANCE else "Fail"
        rows.append({"item": label, "key": key, "reference": ref, "dashboard": ours,
                     "difference": difference, "result": result})
    liabilities_equity = derivation.figures["total_liabilities"].value + derivation.figures[
        "total_equity"].value
    difference = round(liabilities_equity - reference["total_liabilities_and_equity"], 2)
    rows.append({"item": "Total liabilities and equity", "key": "total_liabilities_and_equity",
                 "reference": reference["total_liabilities_and_equity"],
                 "dashboard": round(liabilities_equity, 2), "difference": difference,
                 "result": "Pass" if abs(difference) <= TOLERANCE else "Fail"})
    return rows


# ---------------------------------------------------------------------------
# 3. Ratios and scores, checked by hand formulas
# ---------------------------------------------------------------------------


def _hand_ratios(f: dict, days: int) -> dict[str, float | None]:
    def div(a, b):
        return None if b is None or abs(b) < 1e-9 else a / b

    gross = f["revenue"] - f["cost_of_goods_sold"]
    operating = gross - f["operating_expenses"]
    inventory = f["inventory"] or 0.0
    return {
        "current_ratio": div(f["current_assets"], f["current_liabilities"]),
        "quick_ratio": None if f["inventory"] is None else div(
            f["current_assets"] - inventory, f["current_liabilities"]),
        "gross_profit_margin": None if not f["revenue"] else gross / f["revenue"] * 100,
        "net_profit_margin": None if not f["revenue"] else f["net_profit"] / f["revenue"] * 100,
        "return_on_assets": div(f["net_profit"], f["total_assets"]) and
        div(f["net_profit"] * 365 / days, f["total_assets"]) * 100,
        "debt_to_equity": div(f["total_liabilities"], f["total_equity"])
        if f["total_equity"] > 0 else None,
        "debt_ratio": div(f["total_liabilities"], f["total_assets"]),
        "interest_coverage": div(operating, f["interest_expense"]),
        "asset_turnover": div(f["revenue"] * 365 / days, f["total_assets"]),
        "days_sales_outstanding": None if not f["revenue"] else
        f["accounts_receivable"] / f["revenue"] * days,
    }


def _hand_score(value: float, points, higher_is_better: bool) -> float:
    """Piecewise-linear score through floor 0, distress 40, concern 60, target 100."""
    anchors = [(points.floor, 0.0), (points.distress, 40.0), (points.concern, 60.0),
               (points.target, 100.0)]
    if not higher_is_better:
        anchors = [(-x, s) for x, s in anchors]
        value = -value
    if value <= anchors[0][0]:
        return 0.0
    if value >= anchors[-1][0]:
        return 100.0
    for (x0, s0), (x1, s1) in zip(anchors, anchors[1:]):
        if x0 <= value <= x1:
            return s0 + (value - x0) / (x1 - x0) * (s1 - s0)
    raise AssertionError("unreachable")


def check_scoring(derivation) -> dict:
    values = derivation.record_values()
    days = (PERIOD_END - PERIOD_START).days + 1
    inputs = FinancialInputs(**values, period_days=days)
    validation = validate_financial_inputs(inputs)
    thresholds = _default_thresholds()
    indicators = calculate_indicators(inputs)
    health = assess(indicators, thresholds)
    hand = _hand_ratios(values, days)

    indicator_rows = []
    for scored in health.indicators:
        code = scored.code.value
        expected_value = hand[code]
        threshold = thresholds[scored.code]
        expected_score = None
        if expected_value is not None:
            expected_score = _hand_score(
                expected_value, reference_points_for(threshold),
                threshold.direction.value == "higher_is_better",
            )
        if scored.note and scored.value is None and scored.score is not None:
            expected_score = 0.0  # negative-equity worst case
        value_ok = (scored.value is None and expected_value is None) or (
            scored.value is not None and expected_value is not None
            and abs(scored.value - expected_value) < 1e-6)
        score_ok = (scored.score is None and expected_score is None) or (
            scored.score is not None and expected_score is not None
            and abs(scored.score - expected_score) < 0.02)
        indicator_rows.append({
            "indicator": scored.display_name, "code": code, "category": scored.category.value,
            "engine_value": scored.value, "hand_value": expected_value,
            "engine_score": scored.score, "hand_score": expected_score,
            "status": scored.status.value, "note": scored.note,
            "result": "Pass" if value_ok and score_ok else "Fail",
        })

    # The engine rounds scores to 2 decimals at each step; the hand figures
    # are unrounded, so a difference below 0.02 is rounding, not an error.
    categories = []
    for category, engine_score in health.category_scores.items():
        members = [r["hand_score"] for r in indicator_rows
                   if r["category"] == category.value and r["hand_score"] is not None]
        hand_mean = sum(members) / len(members) if members else None
        ok = (engine_score is None and hand_mean is None) or (
            engine_score is not None and hand_mean is not None
            and abs(engine_score - hand_mean) < 0.02)
        categories.append({"category": category.value, "engine": engine_score,
                           "hand": hand_mean, "result": "Pass" if ok else "Fail"})
    scored_categories = [c["hand"] for c in categories if c["hand"] is not None]
    hand_overall = sum(scored_categories) / len(scored_categories) if scored_categories else None
    overall_ok = abs((health.overall_score or 0) - (hand_overall or 0)) < 0.02

    benchmark = calculate_altman_z_double_prime(inputs)
    return {
        "period_days": days,
        "validation_errors": validation.errors,
        "validation_warnings": validation.warnings,
        "indicators": indicator_rows,
        "categories": categories,
        "overall": {"engine": health.overall_score, "hand": hand_overall,
                    "classification": health.classification.value,
                    "result": "Pass" if overall_ok else "Fail"},
        "benchmark": {"available": benchmark.available, "value": benchmark.value,
                      "missing_inputs": list(benchmark.missing_inputs)},
    }


# ---------------------------------------------------------------------------
# 4. Reconciling the voucher dataset with the reference trial balance
# ---------------------------------------------------------------------------


def _table(wb, name: str) -> list[dict]:
    rows = list(wb[name].iter_rows(values_only=True))
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:] if any(v is not None for v in row)]


def _sum(rows, column) -> float:
    return round(sum(float(r[column] or 0) for r in rows), 2)


def reconcile_vouchers(dataset: Path, statements: Path) -> dict:
    wb = _load(dataset)
    ref = _load(statements)
    tb = {row[0]: (row[2] or 0, row[3] or 0)
          for row in ref["Trial Balance"].iter_rows(min_row=2, values_only=True)
          if row[0] and row[0] != "Totals"}
    sales = _table(wb, "Sales")
    purchases = _table(wb, "Purchases")
    receipts = _table(wb, "Receipts")
    payments = _table(wb, "Payments")
    journal = _table(wb, "Journal")
    contra = _table(wb, "Contra")
    credit_notes = _table(wb, "Credit Notes")
    debit_notes = _table(wb, "Debit Notes")
    stock_items = _table(wb, "Stock Items")
    bills = _table(wb, "Bills of Entry")
    bank = _table(wb, "Bank Statement")
    ledgers = _table(wb, "Ledgers")

    def in_period(rows):
        dates = [datetime.strptime(r["Date"], "%d-%b-%Y").date() for r in rows]
        return all(PERIOD_START <= d <= PERIOD_END for d in dates)

    opening_stock = round(sum(r["Opening Qty"] * r["Opening Rate"] for r in stock_items), 2)
    opening_debtors = round(sum(r["Opening Balance"] or 0 for r in ledgers
                                if r["Group"] == "Sundry Debtors"), 2)
    opening_creditors = round(sum(r["Opening Balance"] or 0 for r in ledgers
                                  if r["Group"] == "Sundry Creditors"), 2)
    supplier_payments = [r for r in payments if str(r["Payee Ledger"]).startswith("Supplier")]
    other_payments = defaultdict(float)
    for r in payments:
        if not str(r["Payee Ledger"]).startswith("Supplier"):
            other_payments[r["Payee Ledger"]] += r["Amount"]

    quantities = defaultdict(float)
    for r in stock_items:
        quantities[r["Stock Item"]] += r["Opening Qty"]
    for r in purchases:
        quantities[r["Item"]] += r["Qty"]
    for r in bills:
        quantities[r["Item"]] += r["Qty"]
    for r in sales:
        quantities[r["Item"]] -= r["Qty"]

    journal_by_type = defaultdict(lambda: {"count": 0, "amount": 0.0, "pairs": set()})
    for r in journal:
        entry = journal_by_type[r["Journal Type"]]
        entry["count"] += 1
        entry["amount"] += r["Amount"]
        entry["pairs"].add(f"Dr {r['Debit Ledger']} / Cr {r['Credit Ledger']}")

    bank_opening = round(bank[0]["Running Balance"] + (
        bank[0]["Amount"] if bank[0]["Type"] == "DR" else -bank[0]["Amount"]), 2)

    checks = [
        {
            "item": "Sales revenue",
            "from_vouchers": round(_sum(sales, "Taxable Value") + _sum(sales, "Freight")
                                   + _sum(sales, "Round Off"), 2),
            "trial_balance": tb["Sales Revenue (Net of GST)"][1],
            "finding": "Equals taxable value + freight charged + round-off. Credit notes "
                       f"({_sum(credit_notes, 'Amount'):,.2f}, including sales returns) are "
                       "not deducted.",
        },
        {
            "item": "Purchases (taxable portion)",
            "from_vouchers": _sum(purchases, "Taxable Value"),
            "trial_balance": tb["Purchases (Taxable Portion)"][0],
            "finding": f"Matches. Debit notes ({_sum(debit_notes, 'Amount'):,.2f}, including "
                       "purchase returns) are not deducted; imports on Bills of Entry "
                       f"(CIF {_sum(bills, 'CIF Value'):,.2f} + duty "
                       f"{_sum(bills, 'BCD (10%)'):,.2f}) are not included.",
        },
        {
            "item": "Output GST (CGST + SGST + IGST)",
            "from_vouchers": round(_sum(sales, "CGST") + _sum(sales, "SGST")
                                   + _sum(sales, "IGST"), 2),
            "trial_balance": round(tb["Output CGST"][1] + tb["Output SGST"][1]
                                   + tb["Output IGST"][1], 2),
            "finding": f"Matches, but output VAT ({_sum(sales, 'VAT'):,.2f}) and CST "
                       f"({_sum(sales, 'CST'):,.2f}) charged on pre-GST sales are missing "
                       "from the trial balance although the VAT Payable and CST Payable "
                       "ledgers exist.",
        },
        {
            "item": "Input GST (CGST + SGST + IGST)",
            "from_vouchers": round(_sum(purchases, "CGST (Input)") + _sum(purchases, "SGST (Input)")
                                   + _sum(purchases, "IGST (Input)"), 2),
            "trial_balance": round(tb["Input CGST"][0] + tb["Input SGST"][0]
                                   + tb["Input IGST"][0], 2),
            "finding": f"Matches. Input VAT ({_sum(purchases, 'VAT (Input)'):,.2f}) and CST "
                       f"({_sum(purchases, 'CST (Input)'):,.2f}) are missing; IGST paid on "
                       f"imports ({_sum(bills, 'IGST (18%)'):,.2f}) is missing.",
        },
        {
            "item": "Freight inward",
            "from_vouchers": _sum(purchases, "Freight Inward"),
            "trial_balance": tb["Freight Inward"][0],
            "finding": "Matches.",
        },
        {
            "item": "Opening stock",
            "from_vouchers": opening_stock,
            "trial_balance": tb["Opening Stock"][0],
            "finding": "Σ opening quantity × opening rate, rounded. It is charged to cost of "
                       "sales, but there is no opening stock asset or matching capital entry, "
                       "so it is absorbed by the capital plug.",
        },
        {
            "item": "Closing stock",
            "from_vouchers": None,
            "trial_balance": tb["Inventory (Closing)"][0],
            "finding": "Set to 0 in the reference. Quantities on hand by item (opening + "
                       "purchases + imports − sales) are: "
                       + ", ".join(f"{k} {v:,.2f}" for k, v in sorted(quantities.items()))
                       + ". Negative quantities mean more was sold than was ever held, and "
                       "purchase and sale rates for the same item vary widely, so no "
                       "defensible closing valuation exists.",
        },
        {
            "item": "Cash and bank",
            "from_vouchers": round(_sum(receipts, "Amount") - _sum(payments, "Amount"), 2),
            "trial_balance": tb["Cash & Bank"][0],
            "finding": "Equals all receipts − all payments. Contra entries net to zero. No "
                       f"opening balance is used, although the bank statement implies an "
                       f"opening bank balance of {bank_opening:,.2f} and ends at "
                       f"{bank[-1]['Running Balance']:,.2f}; the bank statement and the "
                       "vouchers do not reconcile.",
        },
        {
            "item": "Accounts receivable",
            "from_vouchers": round(opening_debtors + _sum(sales, "Grand Total")
                                   - _sum(credit_notes, "Amount") - _sum(receipts, "Amount"), 2),
            "trial_balance": tb["Accounts Receivable"][0],
            "finding": "Opening debtors + invoices − credit notes − receipts. Receipts "
                       f"({_sum(receipts, 'Amount'):,.2f}) are about 7.7 times the year's "
                       "invoiced sales, so customers would have overpaid by millions. The "
                       "reference sets receivables to 0 instead.",
        },
        {
            "item": "Accounts payable",
            "from_vouchers": round(opening_creditors + _sum(purchases, "Invoice Total")
                                   - _sum(debit_notes, "Amount")
                                   - _sum(supplier_payments, "Amount"), 2),
            "trial_balance": -tb["Accounts Payable"][1],
            "finding": "Opening creditors + invoices − debit notes − supplier payments, shown "
                       "with the sign of a debit balance. Supplier payments are about 10 times "
                       "purchases. The reference sets payables to 0 instead.",
        },
        {
            "item": "Transportation charges",
            "from_vouchers": round(other_payments.get("Transportation Charges", 0.0), 2),
            "trial_balance": tb["Transportation Charges"][0],
            "finding": "Payments to the Transportation Charges ledger. Other payments to "
                       "non-supplier ledgers ("
                       + ", ".join(f"{k} {v:,.2f}" for k, v in other_payments.items()
                                   if k != "Transportation Charges")
                       + ") are in cash but not in any expense.",
        },
        {
            "item": "Capital account",
            "from_vouchers": None,
            "trial_balance": tb["Capital Account"][1],
            "finding": "Equals total debits − all other credits: a balancing figure, not a "
                       "recorded capital amount.",
        },
    ]
    for check in checks:
        a, b = check["from_vouchers"], check["trial_balance"]
        check["difference"] = None if a is None else round(a - b, 2)

    return {
        "vouchers_within_period": {
            name: in_period(rows) for name, rows in (
                ("Sales", sales), ("Purchases", purchases), ("Receipts", receipts),
                ("Payments", payments), ("Journal", journal), ("Contra", contra),
                ("Credit Notes", credit_notes), ("Debit Notes", debit_notes))
        },
        "checks": checks,
        "journal": {
            kind: {"count": v["count"], "amount": round(v["amount"], 2),
                   "example_postings": sorted(v["pairs"])[:4]}
            for kind, v in journal_by_type.items()
        },
        "opening_debtors": opening_debtors,
        "opening_creditors": opening_creditors,
    }


# ---------------------------------------------------------------------------


def _jsonable(obj):
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError(type(obj))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--statements", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    pipeline = run_pipeline(args.statements)
    derivation = pipeline.pop("derivation")
    reference = reference_values(args.statements)
    comparison = compare(derivation, reference)
    scoring = check_scoring(derivation)
    vouchers = reconcile_vouchers(args.dataset, args.statements)

    report = {
        "pipeline": pipeline,
        "derivation": {
            "total_debit": derivation.total_debit,
            "total_credit": derivation.total_credit,
            "errors": derivation.errors,
            "warnings": derivation.warnings,
            "figures": {k: f.value for k, f in derivation.figures.items()},
        },
        "comparison": comparison,
        "scoring": scoring,
        "vouchers": vouchers,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "accounting_dataset_validation.json"
    out.write_text(json.dumps(report, indent=2, default=_jsonable, ensure_ascii=False),
                   encoding="utf-8")

    failed = [r["item"] for r in comparison if r["result"] == "Fail"]
    failed += [r["indicator"] for r in scoring["indicators"] if r["result"] == "Fail"]
    failed += [r["category"] for r in scoring["categories"] if r["result"] == "Fail"]
    if scoring["overall"]["result"] == "Fail":
        failed.append("overall")
    print(f"Wrote {out}")
    print("Statement comparison:",
          sum(r["result"] == "Pass" for r in comparison), "pass,",
          sum(r["result"] == "Fail" for r in comparison), "fail,",
          sum(r["result"] == "Not in reference" for r in comparison), "not in reference")
    print("Overall score:", scoring["overall"])
    print("Failures:", failed or "none")


if __name__ == "__main__":
    main()
