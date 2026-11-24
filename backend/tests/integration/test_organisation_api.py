"""API tests for the single-organisation account structure and the overview."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.company import Company, ReportingPeriod
from app.models.financial_record import FinancialRecord
from app.models.user import User
from tests.fixtures.financial_data import SOUND_COMPANY, as_request_payload


def _headers_for(client, email):
    client.post(
        "/api/auth/register",
        json={"email": email, "full_name": "Someone", "password": "correct-horse-battery"},
    )
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "correct-horse-battery"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _set_up(client, headers, name="CrystalCorps"):
    response = client.post(
        "/api/organisation",
        json={"name": name, "industry": "IT", "currency_code": "myr"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _period(client, headers, company, label, start, end):
    response = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": label, "period_start": start, "period_end": end},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _record(client, headers, company, period, **changes):
    payload = as_request_payload(SOUND_COMPANY.model_copy(update=changes), period["id"])
    response = client.post(
        f"/api/companies/{company['id']}/financial-records", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---- One organisation per account ---------------------------------------------


def test_new_account_needs_setup(client, auth_headers):
    body = client.get("/api/organisation", headers=auth_headers).json()
    assert body == {"status": "setup_required", "organisation": None, "candidates": [],
                    "role": None}


def test_setup_creates_the_organisation_once(client, auth_headers):
    created = _set_up(client, auth_headers)
    assert created["currency_code"] == "MYR"
    body = client.get("/api/organisation", headers=auth_headers).json()
    assert body["status"] == "ready"
    assert body["organisation"]["id"] == created["id"]

    again = client.post("/api/organisation", json={"name": "Second"}, headers=auth_headers)
    assert again.status_code == 409
    legacy = client.post("/api/companies", json={"name": "Second"}, headers=auth_headers)
    assert legacy.status_code == 409
    assert client.get("/api/companies", headers=auth_headers).json() == [created]


def test_database_refuses_a_second_organisation(db_session, client, auth_headers):
    created = _set_up(client, auth_headers)
    owner_id = db_session.get(Company, created["id"]).owner_id
    db_session.add(Company(owner_id=owner_id, name="Duplicate", is_primary=True))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---- Accounts that owned several companies before the change -------------------


@pytest.fixture
def ambiguous_account(db_session, client, auth_headers):
    """An account with two companies and no organisation chosen, as the
    migration leaves it."""
    user = db_session.execute(select(User)).scalars().first()
    first = Company(owner_id=user.id, name="Alpha", currency_code="MYR")
    second = Company(owner_id=user.id, name="Beta", currency_code="MYR")
    db_session.add_all([first, second])
    db_session.commit()
    from datetime import date

    db_session.add(ReportingPeriod(company_id=second.id, label="FY2025",
                                   period_start=date(2025, 1, 1), period_end=date(2025, 12, 31)))
    db_session.commit()
    return first.id, second.id


def test_ambiguous_account_must_choose(client, auth_headers, ambiguous_account):
    first, second = ambiguous_account
    body = client.get("/api/organisation", headers=auth_headers).json()
    assert body["status"] == "selection_required"
    assert [c["name"] for c in body["candidates"]] == ["Alpha", "Beta"]
    # Nothing is served until a choice is made.
    assert client.get(f"/api/companies/{first}", headers=auth_headers).status_code == 404
    # Not yet a member of any organisation, so not an admin of one.
    assert client.get("/api/organisation/overview", headers=auth_headers).status_code == 403
    assert client.post("/api/organisation", json={"name": "New"},
                       headers=auth_headers).status_code == 409


def test_choosing_keeps_the_other_company(client, db_session, auth_headers, ambiguous_account):
    first, second = ambiguous_account
    chosen = client.post("/api/organisation/select", json={"company_id": second},
                         headers=auth_headers)
    assert chosen.status_code == 200
    assert client.get("/api/organisation", headers=auth_headers).json()["status"] == "ready"
    overview = client.get("/api/organisation/overview", headers=auth_headers).json()
    assert [p["label"] for p in overview["periods"]] == ["FY2025"]

    # The other company still exists, unchanged, but is not served.
    other = db_session.get(Company, first)
    assert other is not None and other.is_primary is False
    assert client.get(f"/api/companies/{first}", headers=auth_headers).status_code == 404
    # The choice is made once.
    again = client.post("/api/organisation/select", json={"company_id": first},
                        headers=auth_headers)
    assert again.status_code == 409


def test_cannot_choose_another_users_company(client, auth_headers, ambiguous_account):
    other_headers = _headers_for(client, "other@example.com")
    foreign = _set_up(client, other_headers, "Foreign Ltd")
    response = client.post("/api/organisation/select", json={"company_id": foreign["id"]},
                           headers=auth_headers)
    assert response.status_code == 404


# ---- Isolation -----------------------------------------------------------------


def test_another_organisation_is_not_reachable_by_id(client, auth_headers):
    mine = _set_up(client, auth_headers)
    other_headers = _headers_for(client, "other@example.com")
    theirs = _set_up(client, other_headers, "Other Sdn Bhd")
    period = _period(client, other_headers, theirs, "FY2025", "2025-01-01", "2025-12-31")
    _record(client, other_headers, theirs, period)

    for path in (
        f"/api/companies/{theirs['id']}",
        f"/api/companies/{theirs['id']}/reporting-periods",
        f"/api/companies/{theirs['id']}/financial-records",
        f"/api/companies/{theirs['id']}/dashboard/{period['id']}",
    ):
        assert client.get(path, headers=auth_headers).status_code == 404, path
    overview = client.get("/api/organisation/overview", headers=auth_headers).json()
    assert overview["organisation"]["id"] == mine["id"]
    assert overview["periods"] == []


# ---- Overview ------------------------------------------------------------------


def test_overview_without_periods(client, auth_headers):
    _set_up(client, auth_headers)
    body = client.get("/api/organisation/overview", headers=auth_headers).json()
    assert body["periods"] == []
    assert body["latest_period_id"] is None
    assert body["latest_assessed_period_id"] is None


def test_overview_orders_by_date_and_matches_the_dashboard(client, auth_headers):
    company = _set_up(client, auth_headers)
    # Labels sort the wrong way round on purpose: the latest is chosen by date.
    older = _period(client, auth_headers, company, "Year B", "2024-01-01", "2024-12-31")
    newer = _period(client, auth_headers, company, "Year A", "2025-01-01", "2025-12-31")
    empty = _period(client, auth_headers, company, "Q1 2026", "2026-01-01", "2026-03-31")
    _record(client, auth_headers, company, older)
    _record(client, auth_headers, company, newer, revenue=SOUND_COMPANY.revenue * 1.1)

    body = client.get("/api/organisation/overview", headers=auth_headers).json()
    assert [p["label"] for p in body["periods"]] == ["Q1 2026", "Year A", "Year B"]
    assert body["latest_period_id"] == empty["id"]
    assert body["latest_assessed_period_id"] == newer["id"]

    no_data = body["periods"][0]
    assert no_data["status"] == "no_data"
    assert no_data["overall_score"] is None and no_data["classification"] is None
    assert no_data["period_days"] == 90

    latest = body["periods"][1]
    dashboard = client.get(
        f"/api/companies/{company['id']}/dashboard/{newer['id']}", headers=auth_headers
    ).json()["assessment"]
    assert latest["status"] == "assessed"
    assert latest["overall_score"] == dashboard["overall_score"]
    assert latest["classification"] == dashboard["classification"]
    assert latest["category_scores"] == dashboard["category_scores"]
    assert latest["revenue"] == pytest.approx(SOUND_COMPANY.revenue * 1.1)
    assert latest["record"]["revision"] == 1


def test_overview_reports_data_quality_problems(client, auth_headers):
    company = _set_up(client, auth_headers)
    short = _period(client, auth_headers, company, "Jan 2025", "2025-01-01", "2025-01-31")
    # A net profit far from the other lines is stored with a warning.
    _record(client, auth_headers, company, short, net_profit=SOUND_COMPANY.net_profit * 3)
    period = client.get("/api/organisation/overview", headers=auth_headers).json()["periods"][0]
    text = " ".join(period["data_quality_warnings"])
    assert "31" in text  # the unusual period length is called out
    assert "net profit" in text.lower()


def test_overview_includes_trial_balance_warnings(client, auth_headers):
    from tests.fixtures.tally_reference import TALLY_TRIAL_BALANCE, EXPECTED_CATEGORIES

    company = _set_up(client, auth_headers)
    period = _period(client, auth_headers, company, "FY2017-18", "2017-04-01", "2018-03-31")
    lines = [
        {"account_name": name, "account_group": group, "debit": debit, "credit": credit,
         "category": EXPECTED_CATEGORIES[name]}
        for name, group, debit, credit in TALLY_TRIAL_BALANCE
    ]
    response = client.post(f"/api/companies/{company['id']}/trial-balance",
                           json={"reporting_period_id": period["id"], "lines": lines},
                           headers=auth_headers)
    assert response.status_code == 201, response.text
    summary = client.get("/api/organisation/overview", headers=auth_headers).json()["periods"][0]
    assert summary["record"]["source"] == "trial_balance"
    assert summary["overall_score"] == pytest.approx(78.45)
    assert any("closing stock" in w for w in summary["data_quality_warnings"])


def test_existing_revisions_are_preserved(client, db_session, auth_headers):
    company = _set_up(client, auth_headers)
    period = _period(client, auth_headers, company, "FY2025", "2025-01-01", "2025-12-31")
    first = _record(client, auth_headers, company, period)
    payload = as_request_payload(SOUND_COMPANY, period["id"])
    payload.pop("reporting_period_id")
    client.put(f"/api/financial-records/{first['id']}", json=payload, headers=auth_headers)
    revisions = db_session.execute(
        select(FinancialRecord.revision).where(FinancialRecord.reporting_period_id == period["id"])
    ).scalars().all()
    assert sorted(revisions) == [1, 2]
    summary = client.get("/api/organisation/overview", headers=auth_headers).json()["periods"][0]
    assert summary["record"]["revision"] == 2
