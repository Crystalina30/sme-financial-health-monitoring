"""API tests for trial balance input."""

import pytest

from tests.fixtures.financial_data import SOUND_COMPANY, as_request_payload
from tests.fixtures.trial_balance import EXPECTED, sample_payload


def _company(client, headers, name="Acme Trading"):
    company = client.post("/api/companies", json={"name": name}, headers=headers).json()
    period = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "FY2025", "period_start": "2025-01-01", "period_end": "2025-12-31"},
        headers=headers,
    ).json()
    return company, period


def _submit(client, headers, company, period, lines=None):
    return client.post(
        f"/api/companies/{company['id']}/trial-balance",
        json={"reporting_period_id": period["id"], "lines": lines or sample_payload()},
        headers=headers,
    )


def test_categories_are_listed(client, auth_headers):
    response = client.get("/api/trial-balance/categories", headers=auth_headers)
    assert response.status_code == 200
    codes = [category["code"] for category in response.json()]
    assert "revenue" in codes and "non_current_liability" in codes


def test_preview_calculates_without_saving(client, auth_headers):
    company, period = _company(client, auth_headers)
    response = client.post(
        "/api/trial-balance/preview", json={"lines": sample_payload()}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is True
    assert body["figures"]["net_profit"]["value"] == pytest.approx(102_000)
    assert body["figures"]["revenue"]["contributions"][0]["account_name"] == "Sales"
    records = client.get(
        f"/api/companies/{company['id']}/financial-records", headers=auth_headers
    ).json()
    assert records == []


def test_submit_stores_the_derived_figures(client, auth_headers):
    company, period = _company(client, auth_headers)
    response = _submit(client, auth_headers, company, period)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["source"] == "trial_balance"
    assert record["revision"] == 1
    for name, expected in EXPECTED.items():
        assert record[name] == pytest.approx(expected), name


def test_stored_trial_balance_can_be_read_back(client, auth_headers):
    company, period = _company(client, auth_headers)
    record = _submit(client, auth_headers, company, period).json()
    response = client.get(
        f"/api/financial-records/{record['id']}/trial-balance", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["lines"]) == len(sample_payload())
    assert body["lines"][0]["account_name"] == "Maybank current account"
    assert body["derivation"]["figures"]["total_assets"]["value"] == pytest.approx(1_100_000)


def test_resubmitting_stores_a_new_revision(client, auth_headers):
    company, period = _company(client, auth_headers)
    first = _submit(client, auth_headers, company, period).json()
    lines = sample_payload()
    for line in lines:  # move 10,000 of rent into utilities
        if line["account_name"] == "Rent":
            line["debit"] = 50_000
        if line["account_name"] == "Utilities":
            line["debit"] = 30_000
    second = _submit(client, auth_headers, company, period, lines).json()
    assert second["revision"] == first["revision"] + 1
    records = client.get(
        f"/api/companies/{company['id']}/financial-records", headers=auth_headers
    ).json()
    assert [r["id"] for r in records] == [second["id"]]


def test_trial_balance_supersedes_a_statement_record(client, auth_headers):
    company, period = _company(client, auth_headers)
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, period["id"]),
        headers=auth_headers,
    )
    record = _submit(client, auth_headers, company, period).json()
    assert record["revision"] == 2 and record["source"] == "trial_balance"


def test_statement_record_has_no_trial_balance(client, auth_headers):
    company, period = _company(client, auth_headers)
    record = client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, period["id"]),
        headers=auth_headers,
    ).json()
    assert record["source"] == "statement"
    response = client.get(
        f"/api/financial-records/{record['id']}/trial-balance", headers=auth_headers
    )
    assert response.status_code == 404


def test_unbalanced_trial_balance_is_rejected(client, auth_headers):
    company, period = _company(client, auth_headers)
    lines = sample_payload()
    lines[0]["debit"] += 100
    response = _submit(client, auth_headers, company, period, lines)
    assert response.status_code == 422
    assert "does not balance" in " ".join(response.json()["detail"]["errors"])


def test_dashboard_uses_the_derived_figures(client, auth_headers):
    company, period = _company(client, auth_headers)
    _submit(client, auth_headers, company, period)
    response = client.get(
        f"/api/companies/{company['id']}/dashboard/{period['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    assessment = response.json()["assessment"]
    assert assessment["overall_score"] is not None
    current_ratio = next(i for i in assessment["indicators"] if i["code"] == "current_ratio")
    assert current_ratio["value"] == pytest.approx(470_000 / 300_000, rel=1e-3)


def test_suggestions_prefer_the_previous_period(client, auth_headers):
    company, period = _company(client, auth_headers)
    _submit(client, auth_headers, company, period)

    # Account 1300 (Prepayments) comes back under a name the keyword rules do
    # not recognise; the category chosen last period is remembered by code.
    response = client.post(
        f"/api/companies/{company['id']}/trial-balance/suggest",
        json={"lines": [
            {"account_code": "1300", "account_name": "Renamed account"},
            {"account_code": "", "account_name": "Bank overdraft"},
            {"account_code": "9999", "account_name": "Something unusual"},
        ]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
    assert suggestions[0] == {"category": "other_current_asset", "basis": "previous_period"}
    assert suggestions[1] == {"category": "current_liability", "basis": "account_name"}
    assert suggestions[2] == {"category": None, "basis": None}


def test_another_users_record_is_not_found(client, auth_headers):
    company, period = _company(client, auth_headers)
    record = _submit(client, auth_headers, company, period).json()
    client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "full_name": "Other", "password": "correct-horse-battery"},
    )
    token = client.post(
        "/api/auth/login", json={"email": "other@example.com", "password": "correct-horse-battery"}
    ).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    assert client.get(
        f"/api/financial-records/{record['id']}/trial-balance", headers=other
    ).status_code == 404
    assert _submit(client, other, company, period).status_code == 404


def test_excel_import_suggests_categories_and_keeps_the_source(client, auth_headers):
    import io

    import openpyxl

    from tests.fixtures.tally_reference import EXPECTED_CATEGORIES, TALLY_TRIAL_BALANCE

    company, period = _company(client, auth_headers)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Trial Balance"
    ws.append(["Ledger", "Group", "Debit", "Credit"])
    for row in TALLY_TRIAL_BALANCE:
        ws.append(list(row))
    buffer = io.BytesIO()
    wb.save(buffer)

    response = client.post(
        f"/api/companies/{company['id']}/trial-balance/import",
        files={"file": ("statements.xlsx", buffer.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["selected_sheet"] == "Trial Balance"
    lines = body["sheets"][0]["lines"]
    assert {l["account_name"]: l["category"] for l in lines} == EXPECTED_CATEGORIES
    assert all(l["basis"] == "account_group" for l in lines)

    submitted = client.post(
        f"/api/companies/{company['id']}/trial-balance",
        json={"reporting_period_id": period["id"], "lines": [
            {key: l[key] for key in ("account_code", "account_name", "account_group", "debit",
                                     "credit", "category", "source_ref")} for l in lines]},
        headers=auth_headers,
    )
    assert submitted.status_code == 201, submitted.text
    record = submitted.json()
    assert record["cost_of_goods_sold"] == pytest.approx(1983111.23)

    stored = client.get(
        f"/api/financial-records/{record['id']}/trial-balance", headers=auth_headers
    ).json()
    assert stored["lines"][0]["source_ref"] == "statements.xlsx › Trial Balance › row 2"
    assert stored["lines"][0]["account_group"] == "Bank Accounts"
    cogs = stored["derivation"]["figures"]["cost_of_goods_sold"]["contributions"]
    assert cogs[0]["source_ref"].endswith("row 13")


def test_unreadable_upload_is_rejected(client, auth_headers):
    company, _ = _company(client, auth_headers)
    response = client.post(
        f"/api/companies/{company['id']}/trial-balance/import",
        files={"file": ("tb.xls", b"old", "application/vnd.ms-excel")},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "xls" in response.json()["detail"]
