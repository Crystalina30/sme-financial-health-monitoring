"""API tests for correcting and deleting reporting periods."""

import pytest
from sqlalchemy import func, select

from app.models.company import ReportingPeriod
from app.models.financial_record import FinancialRecord
from app.models.trial_balance import TrialBalanceLine
from tests.fixtures.financial_data import SOUND_COMPANY, as_request_payload
from tests.fixtures.trial_balance import sample_payload


def _company(client, headers, name="Acme Trading"):
    return client.post("/api/companies", json={"name": name}, headers=headers).json()


def _period(client, headers, company, label="FY2025", start="2025-01-01", end="2025-01-31"):
    response = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": label, "period_start": start, "period_end": end},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _url(company, period):
    return f"/api/companies/{company['id']}/reporting-periods/{period['id']}"


def _other_headers(client):
    client.post("/api/auth/register", json={
        "email": "other@example.com", "full_name": "Other", "password": "correct-horse-battery"})
    token = client.post("/api/auth/login", json={
        "email": "other@example.com", "password": "correct-horse-battery"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _count(db, model, **where):
    query = select(func.count()).select_from(model)
    for key, value in where.items():
        query = query.where(getattr(model, key) == value)
    return db.execute(query).scalar_one()


# ---- Correcting dates ------------------------------------------------------------


def test_dates_entered_wrongly_can_be_corrected(client, auth_headers):
    company = _company(client, auth_headers)
    period = _period(client, auth_headers, company)  # a month, entered by mistake
    response = client.put(_url(company, period), json={
        "label": "FY2025", "period_start": "2025-01-01", "period_end": "2025-12-31"},
        headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["period_end"] == "2025-12-31"
    listed = client.get(f"/api/companies/{company['id']}/reporting-periods",
                        headers=auth_headers).json()
    assert listed[0]["period_end"] == "2025-12-31"


def test_correcting_dates_keeps_the_data_and_rescales_period_ratios(client, auth_headers):
    company = _company(client, auth_headers)
    period = _period(client, auth_headers, company)
    client.post(f"/api/companies/{company['id']}/financial-records",
                json=as_request_payload(SOUND_COMPANY, period["id"]), headers=auth_headers)
    dashboard = f"/api/companies/{company['id']}/dashboard/{period['id']}"
    before = client.get(dashboard, headers=auth_headers).json()["assessment"]
    assert before["period_days"] == 31

    client.put(_url(company, period), json={
        "label": "FY2025", "period_start": "2025-01-01", "period_end": "2025-12-31"},
        headers=auth_headers)
    after = client.get(dashboard, headers=auth_headers).json()["assessment"]
    assert after["period_days"] == 365
    turnover = {i["code"]: i["value"] for i in after["indicators"]}["asset_turnover"]
    assert turnover == pytest.approx(SOUND_COMPANY.revenue / SOUND_COMPANY.total_assets, rel=1e-3)


def test_correction_is_validated(client, auth_headers):
    company = _company(client, auth_headers)
    period = _period(client, auth_headers, company)
    _period(client, auth_headers, company, label="FY2024", start="2024-01-01", end="2024-12-31")

    backwards = client.put(_url(company, period), json={
        "label": "FY2025", "period_start": "2025-12-31", "period_end": "2025-01-01"},
        headers=auth_headers)
    assert backwards.status_code == 422
    duplicate = client.put(_url(company, period), json={
        "label": "FY2024", "period_start": "2025-01-01", "period_end": "2025-12-31"},
        headers=auth_headers)
    assert duplicate.status_code == 409


# ---- Deleting ----------------------------------------------------------------------


def test_delete_removes_the_period_and_all_its_data(client, db_session, auth_headers):
    company = _company(client, auth_headers)
    period = _period(client, auth_headers, company)
    keep = _period(client, auth_headers, company, label="FY2024", start="2024-01-01",
                   end="2024-12-31")
    # Two revisions for the period being deleted, the second from a trial balance.
    client.post(f"/api/companies/{company['id']}/financial-records",
                json=as_request_payload(SOUND_COMPANY, period["id"]), headers=auth_headers)
    client.post(f"/api/companies/{company['id']}/trial-balance",
                json={"reporting_period_id": period["id"], "lines": sample_payload()},
                headers=auth_headers)
    client.post(f"/api/companies/{company['id']}/financial-records",
                json=as_request_payload(SOUND_COMPANY, keep["id"]), headers=auth_headers)
    assert _count(db_session, FinancialRecord, reporting_period_id=period["id"]) == 2
    assert _count(db_session, TrialBalanceLine) == len(sample_payload())

    response = client.delete(_url(company, period), params={"confirm_label": "FY2025"},
                             headers=auth_headers)
    assert response.status_code == 204

    db_session.expire_all()
    assert db_session.get(ReportingPeriod, period["id"]) is None
    assert _count(db_session, FinancialRecord, reporting_period_id=period["id"]) == 0
    assert _count(db_session, TrialBalanceLine) == 0
    # The other period and its record are untouched.
    assert _count(db_session, FinancialRecord, reporting_period_id=keep["id"]) == 1
    assert client.get(f"/api/companies/{company['id']}/dashboard/{period['id']}",
                      headers=auth_headers).status_code == 404
    overview = client.get("/api/organisation/overview", headers=auth_headers).json()
    assert [p["label"] for p in overview["periods"]] == ["FY2024"]


def test_deleted_label_can_be_used_again(client, auth_headers):
    company = _company(client, auth_headers)
    period = _period(client, auth_headers, company)
    client.delete(_url(company, period), params={"confirm_label": "FY2025"},
                  headers=auth_headers)
    _period(client, auth_headers, company, start="2025-01-01", end="2025-12-31")


def test_another_user_cannot_edit_or_delete(client, auth_headers):
    company = _company(client, auth_headers)
    period = _period(client, auth_headers, company)
    other = _other_headers(client)
    _company(client, other, "Other Co")
    body = {"label": "X", "period_start": "2025-01-01", "period_end": "2025-12-31"}
    assert client.put(_url(company, period), json=body, headers=other).status_code == 404
    assert client.delete(_url(company, period), params={"confirm_label": "FY2025"},
                         headers=other).status_code == 404
    still = client.get(f"/api/companies/{company['id']}/reporting-periods",
                       headers=auth_headers).json()
    assert [p["label"] for p in still] == ["FY2025"]


def test_deleting_a_missing_period_is_not_found(client, auth_headers):
    company = _company(client, auth_headers)
    response = client.delete(f"/api/companies/{company['id']}/reporting-periods/999",
                             params={"confirm_label": "X"}, headers=auth_headers)
    assert response.status_code == 404
