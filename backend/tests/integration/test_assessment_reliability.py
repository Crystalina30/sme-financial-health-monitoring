"""Assessment reliability: Validated, Provisional and Insufficient Data.

Reliability describes the data; the health classification describes the
company. These tests check that the two stay separate, that an income
statement which does not add up is never presented as validated, and that
correcting a record updates the status without touching earlier revisions.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.financial_record import FinancialRecord
from app.services.validation_service import reconcile_income_statement
from tests.fixtures.financial_data import SOUND_COMPANY, as_request_payload
from tests.fixtures.tally_reference import EXPECTED_CATEGORIES, TALLY_TRIAL_BALANCE
from tests.fixtures.trial_balance import sample_payload

# The inconsistent statement from the problem report: revenue mistyped as
# 1,200, net profit reported as 100,000.
INCONSISTENT = {
    "revenue": 1_200, "cost_of_goods_sold": 780_000, "operating_expenses": 260_000,
    "interest_expense": 30_000, "tax_expense": 30_000, "net_profit": 100_000,
}


def _consistent(**changes):
    """SOUND_COMPANY with net profit set to what its lines imply."""
    data = SOUND_COMPANY.model_copy(update=changes)
    implied = reconcile_income_statement(data).calculated_net_profit
    return data.model_copy(update={"net_profit": float(implied)})


@pytest.fixture
def org(client, auth_headers):
    company = client.post("/api/organisation", json={"name": "Acme"}, headers=auth_headers).json()

    def period(label="FY2025", start="2025-01-01", end="2025-12-31"):
        return client.post(
            f"/api/companies/{company['id']}/reporting-periods",
            json={"label": label, "period_start": start, "period_end": end},
            headers=auth_headers,
        ).json()

    def enter(data, p):
        response = client.post(
            f"/api/companies/{company['id']}/financial-records",
            json=as_request_payload(data, p["id"]), headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        return response.json()

    def dashboard(p):
        response = client.get(f"/api/companies/{company['id']}/dashboard/{p['id']}",
                              headers=auth_headers)
        assert response.status_code == 200, response.text
        return response.json()

    return company, period, enter, dashboard


def test_consistent_statement_is_validated(org):
    _, period, enter, dashboard = org
    p = period()
    enter(_consistent(), p)
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "validated"
    assert a["is_provisional"] is False
    assert a["income_statement_reconciliation"]["reconciled"] is True
    assert a["reconciliation_difference"] == pytest.approx(0)
    # Reliability does not replace the health classification.
    assert a["classification"] in ("sound", "vulnerable", "distressed")


def test_loss_making_but_consistent_statement_is_validated(org):
    _, period, enter, dashboard = org
    p = period()
    enter(_consistent(cost_of_goods_sold=1_100_000), p)
    a = dashboard(p)["assessment"]
    assert a["calculated_net_profit"] < 0
    assert a["assessment_status"] == "validated"
    severities = {i["code"]: i["severity"] for i in a["data_quality_issues"]}
    assert severities.get("negative_gross_profit") == "info"


def test_the_reported_inconsistency_is_provisional_with_exact_figures(org):
    _, period, enter, dashboard = org
    p = period()
    record = enter(SOUND_COMPANY.model_copy(update=INCONSISTENT), p)
    # Stored as entered: nothing is adjusted to make it reconcile.
    assert record["revenue"] == 1_200 and record["net_profit"] == 100_000

    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "provisional"
    assert a["is_provisional"] is True
    assert a["overall_score"] is not None  # an indicative score is still shown
    assert a["reported_net_profit"] == pytest.approx(100_000)
    assert a["calculated_net_profit"] == pytest.approx(-1_098_800)
    assert a["reconciliation_difference"] == pytest.approx(1_198_800)
    rec = a["income_statement_reconciliation"]
    assert rec["gross_profit"] == pytest.approx(-778_800)
    assert rec["operating_profit"] == pytest.approx(-1_038_800)
    material = [i for i in a["data_quality_issues"] if i["severity"] == "material"]
    assert any("1,198,800.00" in i["message"] for i in material)


def test_legitimate_other_income_reconciles(org):
    _, period, enter, dashboard = org
    p = period()
    # Net profit 20,000 higher than the core lines imply, explained by
    # 25,000 of non-operating income and 5,000 of non-operating expenses.
    base = _consistent()
    data = base.model_copy(update={
        "net_profit": base.net_profit + 20_000, "other_income": 25_000, "other_expenses": 5_000,
    })
    enter(data, p)
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "validated"
    rec = a["income_statement_reconciliation"]
    assert rec["other_income"] == pytest.approx(25_000)
    assert rec["profit_before_tax"] - rec["tax_expense"] == pytest.approx(
        rec["calculated_net_profit"])


def test_other_operating_income_counts_in_operating_profit(org):
    _, period, enter, dashboard = org
    p = period()
    base = _consistent()
    data = base.model_copy(update={
        "net_profit": base.net_profit + 10_000, "other_operating_income": 10_000})
    enter(data, p)
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "validated"
    summary = dashboard(p)["financial_summary"]
    assert summary["operating_profit"] == pytest.approx(
        SOUND_COMPANY.revenue - SOUND_COMPANY.cost_of_goods_sold
        - SOUND_COMPANY.operating_expenses + 10_000)


def test_a_one_cent_difference_is_tolerated_and_two_cents_are_not(org):
    _, period, enter, dashboard = org
    base = _consistent()
    p1, p2 = period("A", "2024-01-01", "2024-12-31"), period("B", "2025-01-01", "2025-12-31")
    enter(base.model_copy(update={"net_profit": base.net_profit + 0.01}), p1)
    enter(base.model_copy(update={"net_profit": base.net_profit + 0.02}), p2)
    assert dashboard(p1)["assessment"]["assessment_status"] == "validated"
    assert dashboard(p2)["assessment"]["assessment_status"] == "provisional"


def test_missing_essential_figures_give_insufficient_data(org):
    _, period, enter, dashboard = org
    p = period()
    zeros = {name: 0 for name in (
        "revenue", "cost_of_goods_sold", "operating_expenses", "interest_expense",
        "tax_expense", "net_profit", "cash_and_equivalents", "accounts_receivable",
        "current_assets", "total_assets", "current_liabilities", "total_liabilities",
        "total_equity")}
    enter(SOUND_COMPANY.model_copy(update={**zeros, "inventory": None}), p)
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "insufficient_data"
    assert a["overall_score"] is None
    assert any(i["code"] == "insufficient_data" for i in a["data_quality_issues"])


def test_balance_sheet_failure_is_still_rejected(client, auth_headers, org):
    company, period, _, _ = org
    p = period()
    broken = _consistent(total_assets=SOUND_COMPANY.total_assets + 0.02)
    response = client.post(f"/api/companies/{company['id']}/financial-records",
                           json=as_request_payload(broken, p["id"]), headers=auth_headers)
    assert response.status_code == 422


# ---- Trial balance ---------------------------------------------------------------


def _submit_tb(client, auth_headers, company, p, lines):
    response = client.post(f"/api/companies/{company['id']}/trial-balance",
                           json={"reporting_period_id": p["id"], "lines": lines},
                           headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_correctly_mapped_trial_balance_is_validated(client, auth_headers, org):
    company, period, _, dashboard = org
    p = period()
    record = _submit_tb(client, auth_headers, company, p, sample_payload())
    # The sample's 2,000 of interest received is carried as other income,
    # so the statement reconciles.
    assert record["other_income"] == pytest.approx(2_000)
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "validated", a["data_quality_issues"]


def test_trial_balance_without_closing_stock_is_provisional(client, auth_headers, org):
    company, period, _, dashboard = org
    p = period("FY2017-18", "2017-04-01", "2018-03-31")
    lines = [{"account_name": n, "account_group": g, "debit": d, "credit": c,
              "category": EXPECTED_CATEGORIES[n]} for n, g, d, c in TALLY_TRIAL_BALANCE]
    _submit_tb(client, auth_headers, company, p, lines)
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "provisional"
    assert any(i["code"] == "missing_closing_stock" for i in a["data_quality_issues"])
    # The figures reconcile; it is the missing closing stock that is material.
    assert a["income_statement_reconciliation"]["reconciled"] is True
    assert a["overall_score"] == pytest.approx(78.45)  # scoring unchanged


def test_post_closing_trial_balance_is_not_validated(client, auth_headers, org):
    company, period, _, dashboard = org
    p = period()
    balance_sheet_only = [
        line for line in sample_payload()
        if line["category"] not in {"revenue", "other_income", "cost_of_sales",
                                    "operating_expense", "interest_expense", "tax_expense"}
    ]
    for line in balance_sheet_only:  # move the year's profit into retained earnings
        if line["category"] == "retained_earnings":
            line["credit"] += 102_000
    _submit_tb(client, auth_headers, company, p, balance_sheet_only)
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] in ("provisional", "insufficient_data")
    assert a["assessment_status"] != "validated"
    assert any(i["code"] == "post_closing_trial_balance" for i in a["data_quality_issues"])


# ---- Revisions, history and the overview ------------------------------------------


def test_correcting_a_record_updates_the_status_and_keeps_history(
    client, auth_headers, db_session, org
):
    company, period, enter, dashboard = org
    older = period("FY2024", "2024-01-01", "2024-12-31")
    current = period("FY2025", "2025-01-01", "2025-12-31")
    enter(_consistent(), older)
    first = enter(SOUND_COMPANY.model_copy(update=INCONSISTENT), current)
    assert dashboard(current)["assessment"]["assessment_status"] == "provisional"

    trend = dashboard(current)["score_trend"]
    assert [(t["period_label"], t["assessment_status"]) for t in trend] == [
        ("FY2024", "validated"), ("FY2025", "provisional")]

    corrected = as_request_payload(_consistent(), current["id"])
    corrected.pop("reporting_period_id")
    response = client.put(f"/api/financial-records/{first['id']}", json=corrected,
                          headers=auth_headers)
    assert response.status_code == 200
    assert dashboard(current)["assessment"]["assessment_status"] == "validated"
    assert [t["assessment_status"] for t in dashboard(current)["score_trend"]] == [
        "validated", "validated"]

    # The earlier revision is kept exactly as entered.
    old = db_session.execute(
        select(FinancialRecord).where(FinancialRecord.id == first["id"])
    ).scalar_one()
    assert old.is_current is False
    assert Decimal(str(old.revenue)) == Decimal("1200")
    assert Decimal(str(old.net_profit)) == Decimal("100000")


def test_overview_reports_each_periods_status(client, auth_headers, org):
    _, period, enter, _ = org
    ok, bad, empty = (period("FY2023", "2023-01-01", "2023-12-31"),
                      period("FY2024", "2024-01-01", "2024-12-31"),
                      period("FY2025", "2025-01-01", "2025-12-31"))
    enter(_consistent(), ok)
    enter(SOUND_COMPANY.model_copy(update=INCONSISTENT), bad)
    periods = {p["label"]: p for p in
               client.get("/api/organisation/overview", headers=auth_headers).json()["periods"]}
    assert periods["FY2023"]["assessment_status"] == "validated"
    assert periods["FY2024"]["assessment_status"] == "provisional"
    assert periods["FY2024"]["is_provisional"] is True
    assert periods["FY2024"]["reconciliation_difference"] == pytest.approx(1_198_800)
    assert "1,198,800.00" in periods["FY2024"]["data_quality_warnings"][0]
    assert periods["FY2025"]["assessment_status"] is None


# ---- What "checks passed" means ----------------------------------------------------


def test_the_checks_performed_are_listed(org):
    _, period, enter, dashboard = org
    p = period()
    enter(_consistent(), p)
    checks = {c["name"]: c for c in dashboard(p)["assessment"]["checks_performed"]}
    assert checks["Balance sheet balances (assets = liabilities + equity)"]["passed"] is True
    assert checks["Net profit reconciles with the income statement lines"]["passed"] is True
    # Statement totals cannot be checked for completeness account by account.
    assert checks["Trial balance checks"]["passed"] is None
    assert "could not be checked" in checks["Trial balance checks"]["detail"]


def test_trial_balance_records_list_their_account_level_checks(client, auth_headers, org):
    company, period, _, dashboard = org
    p = period()
    _submit_tb(client, auth_headers, company, p, sample_payload())
    checks = {c["name"]: c for c in dashboard(p)["assessment"]["checks_performed"]}
    assert checks["Period-end stock is accounted for"]["passed"] is True
    assert "Periodic inventory, adjusted" in checks["Period-end stock is accounted for"]["detail"]


# ---- Rounded published statements ----------------------------------------------------


def test_a_statement_rounded_to_thousands_is_checked_with_its_own_tolerance(
    client, auth_headers, org
):
    company, period, _, dashboard = org
    p = period()
    # Published in thousands and entered as full amounts: the balance sheet
    # is out by 1,000 and net profit by 2,000, both within rounding.
    base = _consistent()
    data = base.model_copy(update={
        "total_equity": base.total_equity - 1_000, "net_profit": base.net_profit + 2_000})
    payload = as_request_payload(data, p["id"])

    exact = client.post(f"/api/companies/{company['id']}/financial-records",
                        json=payload, headers=auth_headers)
    assert exact.status_code == 422  # as exact figures, the balance sheet fails

    payload["presentation_unit"] = 1000
    rounded = client.post(f"/api/companies/{company['id']}/financial-records",
                          json=payload, headers=auth_headers)
    assert rounded.status_code == 201, rounded.text
    assert rounded.json()["presentation_unit"] == 1000
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "validated"
    assert a["presentation_unit"] == 1000
    assert any(i["code"] == "rounded_source" for i in a["data_quality_issues"])


def test_an_unsupported_precision_is_refused(client, auth_headers, org):
    company, period, _, _ = org
    payload = as_request_payload(_consistent(), period()["id"])
    payload["presentation_unit"] = 500
    response = client.post(f"/api/companies/{company['id']}/financial-records",
                           json=payload, headers=auth_headers)
    assert response.status_code == 422


# ---- Inventory: closing stock is never assumed to be zero --------------------------


def _tally_lines():
    return [{"account_name": n, "account_group": g, "debit": d, "credit": c,
             "category": EXPECTED_CATEGORIES[n],
             "source_ref": f"Financial_Statements_FY2017-18.xlsx › Trial Balance › row {i}"}
            for i, (n, g, d, c) in enumerate(TALLY_TRIAL_BALANCE, start=2)]


def test_tally_trial_balance_needs_a_stock_count(client, auth_headers):
    response = client.post("/api/trial-balance/preview", json={"lines": _tally_lines()},
                           headers=auth_headers)
    inventory = response.json()["inventory"]
    assert inventory["method"] == "periodic_unadjusted"
    assert inventory["needs_closing_stock"] is True
    assert any("Inventory (Closing), row 3" in w for w in response.json()["warnings"])


def test_entering_the_stock_count_adjusts_cogs_and_inventory(client, auth_headers, org):
    company, period, _, dashboard = org
    p = period("FY2017-18", "2017-04-01", "2018-03-31")
    count = 250_000.0
    lines = _tally_lines() + [
        {"account_name": "Closing stock (period-end adjustment)", "debit": count, "credit": 0,
         "category": "inventory", "source_ref": "Period-end adjustment: stock count entered by user"},
        {"account_name": "Closing stock (period-end adjustment)", "debit": 0, "credit": count,
         "category": "cost_of_sales", "source_ref": "Period-end adjustment: stock count entered by user"},
    ]
    record = _submit_tb(client, auth_headers, company, p, lines)
    assert record["cost_of_goods_sold"] == pytest.approx(1_983_111.23 - count)
    assert record["inventory"] == pytest.approx(count)
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "validated", a["data_quality_issues"]


def test_confirming_no_closing_stock_is_recorded_and_traceable(client, auth_headers, org):
    company, period, _, dashboard = org
    p = period("FY2017-18", "2017-04-01", "2018-03-31")
    lines = _tally_lines() + [
        {"account_name": "Closing stock (period-end adjustment: confirmed nil)", "debit": 0,
         "credit": 0, "category": "cost_of_sales",
         "source_ref": "Period-end adjustment: no closing stock, confirmed by user"},
    ]
    _submit_tb(client, auth_headers, company, p, lines)
    a = dashboard(p)["assessment"]
    assert a["assessment_status"] == "validated"
    notes = {i["code"]: i["severity"] for i in a["data_quality_issues"]}
    assert notes["closing_stock_confirmed_nil"] == "info"
    assert a["overall_score"] == pytest.approx(78.45)  # same figures, same score
