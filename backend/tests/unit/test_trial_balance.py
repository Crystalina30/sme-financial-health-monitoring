"""Unit tests for deriving statement figures from a trial balance."""

import pytest

from app.services.trial_balance_service import (
    CATEGORY_BY_CODE,
    FIGURE_FORMULAS,
    Line,
    derive,
    suggest_category,
)
from app.services.validation_service import check_accounting_identity
from app.schemas.financial_record import FinancialRecordUpdateRequest
from tests.fixtures.trial_balance import EXPECTED, SAMPLE_ROWS


def _lines(rows=SAMPLE_ROWS):
    return [
        Line(i, code, name, float(debit), float(credit), category)
        for i, (code, name, debit, credit, category) in enumerate(rows, start=1)
    ]


def _replace(code, **changes):
    rows = []
    for row in SAMPLE_ROWS:
        if row[0] == code:
            fields = dict(zip(("code", "name", "debit", "credit", "category"), row))
            fields.update(changes)
            row = tuple(fields.values())
        rows.append(row)
    return rows


def test_sample_trial_balance_balances():
    result = derive(_lines())
    assert result.total_debit == result.total_credit == pytest.approx(2_510_000)
    assert result.is_valid, result.errors


@pytest.mark.parametrize("name,expected", sorted(EXPECTED.items()))
def test_sample_figures(name, expected):
    assert derive(_lines()).figures[name].value == pytest.approx(expected)


def test_every_figure_has_a_formula():
    result = derive(_lines())
    assert set(result.figures) == set(FIGURE_FORMULAS)
    assert all(figure.formula for figure in result.figures.values())


def test_contra_accounts_reduce_their_category():
    figures = derive(_lines()).figures
    revenue = {c.account_name: c.amount for c in figures["revenue"].contributions}
    assert revenue == {"Sales": 1_250_000, "Sales returns": -50_000}
    cogs = {c.account_name: c.amount for c in figures["cost_of_goods_sold"].contributions}
    assert cogs["Closing stock"] == -150_000


def test_contributions_add_up_to_each_figure():
    for name, figure in derive(_lines()).figures.items():
        if name == "inventory" or figure.value is None:
            continue
        total = sum(c.amount for c in figure.contributions)
        if name in ("total_equity", "retained_earnings"):
            continue  # also includes net profit, checked below
        assert total == pytest.approx(figure.value), name


def test_equity_includes_the_period_profit():
    figures = derive(_lines()).figures
    assert figures["total_equity"].value == pytest.approx(300_000 + 98_000 + 102_000)
    assert sum(c.amount for c in figures["total_equity"].contributions) == pytest.approx(
        figures["total_equity"].value
    )


def test_balanced_trial_balance_satisfies_the_accounting_identity():
    values = derive(_lines()).values()
    inputs = FinancialRecordUpdateRequest(**values).to_financial_inputs()
    holds, difference = check_accounting_identity(inputs)
    assert holds and difference == pytest.approx(0)


def test_unbalanced_trial_balance_is_rejected():
    result = derive(_lines(_replace("4000", credit=1_250_100)))
    assert not result.is_valid
    assert result.difference == pytest.approx(-100)
    assert any("does not balance" in error for error in result.errors)


def test_uncategorised_row_is_rejected():
    result = derive(_lines(_replace("6010", category=None)))
    assert any("Row 24 (Rent) has no category" in error for error in result.errors)


def test_unknown_category_is_rejected():
    result = derive(_lines(_replace("6010", category="misc")))
    assert any("unknown category" in error for error in result.errors)


def test_empty_trial_balance_is_rejected():
    assert "The trial balance has no rows." in derive([]).errors


def test_negative_figure_is_reported():
    # Putting the debtors on the wrong side makes receivables negative.
    rows = _replace("1100", debit=0, credit=190_000)
    rows = _replace_in(rows, "1000", debit=495_000)
    result = derive(_lines(rows))
    assert any("Trade receivables works out negative" in e for e in result.errors)


def _replace_in(rows, code, **changes):
    out = []
    for row in rows:
        if row[0] == code:
            fields = dict(zip(("code", "name", "debit", "credit", "category"), row))
            fields.update(changes)
            row = tuple(fields.values())
        out.append(row)
    return out


def test_inventory_is_not_reported_without_inventory_accounts():
    rows = [row for row in SAMPLE_ROWS if row[0] != "1200"]
    rows = _replace_in(rows, "1000", debit=265_000)
    result = derive(_lines(rows))
    assert result.is_valid
    assert result.figures["inventory"].value is None
    assert result.figures["current_assets"].value == pytest.approx(470_000)


def test_retained_earnings_not_reported_without_its_accounts():
    rows = _replace("3100", category="equity")
    figures = derive(_lines(rows)).figures
    assert figures["retained_earnings"].value is None
    assert figures["total_equity"].value == pytest.approx(500_000)


def test_post_closing_trial_balance_is_warned_about():
    # After closing, income and expense accounts are zero and the profit sits
    # in retained earnings.
    rows = [row for row in SAMPLE_ROWS if row[4] in
            {c for c, cat in CATEGORY_BY_CODE.items() if cat.statement == "balance_sheet"}]
    rows = _replace_in(rows, "3100", credit=200_000)
    result = derive(_lines(rows))
    assert result.is_valid
    assert any("after closing" in warning for warning in result.warnings)


def test_duplicate_account_codes_are_warned_about():
    rows = SAMPLE_ROWS + [("6010", "Rent (duplicate)", 0, 0, "operating_expense")]
    assert any("6010" in warning for warning in derive(_lines(rows)).warnings)


def test_negative_amounts_are_rejected():
    result = derive([Line(1, "1", "Cash", -5, 0, "cash"), Line(2, "2", "Capital", 0, -5, "equity")])
    assert any("must not be negative" in error for error in result.errors)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Sales", "revenue"),
        ("Sales returns", "revenue"),
        ("Cost of sales", "cost_of_sales"),
        ("Purchases", "cost_of_sales"),
        ("Closing stock", "cost_of_sales"),
        ("Stock", "inventory"),
        ("Bank charges", "operating_expense"),
        ("Maybank current account", "cash"),
        ("Bank overdraft", "current_liability"),
        ("Short-term loan", "current_liability"),
        ("Term loan", "non_current_liability"),
        ("Interest on hire purchase", "interest_expense"),
        ("Interest received", "other_income"),
        ("Accumulated depreciation - motor vehicles", "non_current_asset"),
        ("Motor vehicle expenses", "operating_expense"),
        ("Allowance for doubtful debts", "accounts_receivable"),
        ("Accrued expenses", "current_liability"),
        ("Prepaid expenses", "other_current_asset"),
        ("SST payable", "current_liability"),
        ("Income tax", "tax_expense"),
        ("Retained earnings", "retained_earnings"),
        ("Drawings", "equity"),
        ("Something unusual", None),
    ],
)
def test_category_suggestions(name, expected):
    assert suggest_category(name) == expected


def test_sample_rows_are_suggested_correctly():
    # The keyword rules recognise every account in the sample.
    for _, name, _, _, category in SAMPLE_ROWS:
        assert suggest_category(name) == category, name


def test_other_income_and_expense_lines_reach_net_profit():
    rows = SAMPLE_ROWS + [
        ("4950", "Wage subsidy", 0, 6_000, "other_operating_income"),
        ("6900", "Loss on disposal of equipment", 4_000, 0, "other_expense"),
    ]
    # Keep it balanced: the subsidy came in as cash, the loss reduced equipment.
    rows = [(*r[:2], r[2] + 6_000, *r[3:]) if r[0] == "1000" else r for r in rows]
    rows = [(*r[:3], r[3] + 4_000, r[4]) if r[0] == "1520" else r for r in rows]
    result = derive(_lines(rows))
    assert result.is_valid, result.errors
    figures = result.figures
    assert figures["other_operating_income"].value == pytest.approx(6_000)
    assert figures["other_income"].value == pytest.approx(2_000)
    assert figures["other_expenses"].value == pytest.approx(4_000)
    assert figures["operating_profit"].value == pytest.approx(1_200_000 - 780_000 + 6_000 - 260_000)
    assert figures["net_profit"].value == pytest.approx(102_000 + 6_000 - 4_000)
    values = result.record_values()
    assert values["other_operating_income"] == pytest.approx(6_000)


def test_trial_balance_findings_carry_a_severity():
    rows = [r for r in SAMPLE_ROWS if r[0] != "5090"]  # drop the closing stock credit
    # ... and the stock balance with it, which keeps the trial balance balanced.
    rows = [(*r[:2], 0, 0, r[4]) if r[0] == "1200" else r for r in rows]
    result = derive(_lines(rows))
    codes = {code: severity for severity, code, _ in result.findings}
    assert codes.get("missing_closing_stock") == "material"


@pytest.mark.parametrize("name,expected", [
    ("Loss on disposal of equipment", "other_expense"),
    ("Foreign exchange loss", "other_expense"),
    ("Wage subsidy received", "other_operating_income"),
])
def test_new_category_suggestions(name, expected):
    assert suggest_category(name) == expected


# ---- Inventory method ----------------------------------------------------------------


def test_adjusted_periodic_inventory_is_recognised():
    result = derive(_lines())
    assert result.inventory.method == "periodic_adjusted"
    assert not result.inventory.needs_closing_stock


def test_perpetual_inventory_is_recognised():
    # Cost of sales posted directly; the stock account holds closing stock.
    rows = [r for r in SAMPLE_ROWS if r[4] != "cost_of_sales"]
    rows.append(("5000", "Cost of goods sold", 780_000, 0, "cost_of_sales"))
    result = derive(_lines(rows))
    assert result.is_valid, result.errors
    assert result.inventory.method == "perpetual"
    assert not [f for f in result.findings if f[0] == "material"]


def test_unadjusted_trial_balance_with_opening_stock_in_inventory_is_flagged():
    # Textbook unadjusted periodic trial balance: the stock account still
    # holds opening stock and only purchases are in cost of sales.
    rows = [r for r in SAMPLE_ROWS if r[0] not in ("5000", "5090")]
    rows = [(*r[:2], 140_000, *r[3:]) if r[0] == "1200" else r for r in rows]
    result = derive(_lines(rows))
    assert result.is_valid, result.errors
    assert result.inventory.method == "periodic_opening_in_inventory"
    assert result.inventory.opening_balance_in_inventory == pytest.approx(140_000)
    assert ("material", "inventory_may_be_opening_stock") in {
        (f[0], f[1]) for f in result.findings}


def test_closing_stock_credit_must_match_the_inventory_balance():
    rows = [(*r[:2], 151_000, *r[3:]) if r[0] == "1200" else r for r in SAMPLE_ROWS]
    rows = [(*r[:3], r[3] + 1_000, r[4]) if r[0] == "3100" else r for r in rows]
    result = derive(_lines(rows))
    assert ("material", "closing_stock_mismatch") in {(f[0], f[1]) for f in result.findings}


def test_service_business_has_no_stock_treatment():
    rows = [r for r in SAMPLE_ROWS if r[4] not in ("cost_of_sales", "inventory")]
    result = derive(_lines(rows))
    assert result.inventory.method == "none"


# ---- Audit items 2 and 3: no stock or cost-of-sales conclusion by absence -----


def _audit_lines(rows):
    return [Line(i, "", name, float(d), float(c), cat) for i, (name, d, c, cat) in
            enumerate(rows, start=1)]


def test_purchases_without_stock_accounts_need_a_count_or_confirmation():
    # The audit's reproduction: revenue 200, purchases 100, cash 100.
    result = derive(_audit_lines([("Sales", 0, 200, "revenue"),
                                  ("Purchases", 100, 0, "cost_of_sales"),
                                  ("Cash", 100, 0, "cash")]))
    assert result.is_valid
    assert result.inventory.method == "purchases_only"
    assert result.inventory.needs_closing_stock
    assert ("material", "stock_not_confirmed") in {(f[0], f[1]) for f in result.findings}


def test_confirming_no_stock_clears_the_purchases_only_finding():
    lines = _audit_lines([("Sales", 0, 200, "revenue"), ("Purchases", 100, 0, "cost_of_sales"),
                          ("Cash", 100, 0, "cash")])
    lines.append(Line(4, "", "Closing stock (period-end adjustment: confirmed nil)", 0, 0,
                      "cost_of_sales", "", "Period-end adjustment: no closing stock, confirmed"))
    result = derive(lines)
    assert not [f for f in result.findings if f[0] == "material"]


def test_counting_stock_for_purchases_only_adjusts_cogs():
    lines = _audit_lines([("Sales", 0, 200, "revenue"), ("Purchases", 100, 0, "cost_of_sales"),
                          ("Cash", 100, 0, "cash")])
    ref = "Period-end adjustment: stock count"
    lines += [Line(4, "", "Closing stock (period-end adjustment)", 30, 0, "inventory", "", ref),
              Line(5, "", "Closing stock (period-end adjustment)", 0, 30, "cost_of_sales", "", ref)]
    result = derive(lines)
    assert result.inventory.method == "periodic_adjusted"
    assert result.figures["cost_of_goods_sold"].value == pytest.approx(70)
    assert result.figures["inventory"].value == pytest.approx(30)


def test_cogs_account_mixed_with_purchases_needs_review():
    # The audit's reproduction: purchases 200 and cost of goods sold 150.
    result = derive(_audit_lines([("Sales", 0, 500, "revenue"),
                                  ("Purchases", 200, 0, "cost_of_sales"),
                                  ("Cost of goods sold", 150, 0, "cost_of_sales"),
                                  ("Cash", 150, 0, "cash")]))
    assert result.inventory.method == "mixed_unreviewed"
    assert result.inventory.needs_review
    assert ("material", "mixed_cost_of_sales") in {(f[0], f[1]) for f in result.findings}


def test_mixed_postings_can_be_confirmed_by_the_user():
    lines = _audit_lines([("Sales", 0, 500, "revenue"), ("Purchases", 200, 0, "cost_of_sales"),
                          ("Cost of goods sold", 150, 0, "cost_of_sales"),
                          ("Cash", 150, 0, "cash")])
    lines.append(Line(5, "", "Cost of sales reviewed: separate costs (period-end adjustment)",
                      0, 0, "cost_of_sales", "", "Period-end adjustment: confirmed by user"))
    result = derive(lines)
    assert result.inventory.method == "mixed_reviewed"
    assert not [f for f in result.findings if f[0] == "material"]


def test_perpetual_inventory_with_purchases_to_inventory_is_accepted():
    # The correct perpetual mapping: purchases debited to inventory.
    result = derive(_audit_lines([("Sales", 0, 500, "revenue"),
                                  ("Cost of goods sold", 150, 0, "cost_of_sales"),
                                  ("Stock (purchases capitalised)", 50, 0, "inventory"),
                                  ("Cash", 300, 0, "cash")]))
    assert result.inventory.method == "perpetual"
    assert not [f for f in result.findings if f[0] == "material"]


def test_import_refuses_non_finite_amounts():
    from app.services.trial_balance_import import parse_amount, parse_balance
    for text in ("inf", "-inf", "nan", "1e999", float("inf"), float("nan")):
        assert parse_amount(text) is None
    assert parse_balance("inf Dr") is None
