"""One organisation, several users: CEO / Admin and Finance Clerk.

Every rule of the permission table is checked on the API itself, so it holds
whatever the interface shows.
"""

import pytest

from tests.fixtures.financial_data import SOUND_COMPANY, as_request_payload
from tests.fixtures.trial_balance import sample_payload

PASSWORD = "correct-horse-battery"


def _register(client, email, name="Someone"):
    client.post("/api/auth/register",
                json={"email": email, "full_name": name, "password": PASSWORD})
    token = client.post("/api/auth/login",
                        json={"email": email, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org(client, auth_headers):
    """CrystalCorps with one period and record, its CEO, and a Finance Clerk."""
    company = client.post("/api/organisation", json={"name": "CrystalCorps"},
                          headers=auth_headers).json()
    period = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "FY2025", "period_start": "2025-01-01", "period_end": "2025-12-31"},
        headers=auth_headers).json()
    record = client.post(f"/api/companies/{company['id']}/financial-records",
                         json=as_request_payload(SOUND_COMPANY, period["id"]),
                         headers=auth_headers).json()
    clerk = _register(client, "clerk@example.com", "Finance Clerk")
    invitation = client.post("/api/organisation/invitations",
                             json={"email": "clerk@example.com", "role": "clerk"},
                             headers=auth_headers)
    assert invitation.status_code == 201, invitation.text
    accepted = client.post("/api/organisation/invitations/accept",
                           json={"token": invitation.json()["token"]}, headers=clerk)
    assert accepted.status_code == 200, accepted.text
    members = client.get("/api/organisation/members", headers=auth_headers).json()
    member_id = next(m["id"] for m in members if m["email"] == "clerk@example.com")
    return {"company": company, "period": period, "record": record,
            "admin": auth_headers, "clerk": clerk, "member_id": member_id}


def _url(org, path=""):
    return f"/api/companies/{org['company']['id']}{path}"


# ---- Roles -------------------------------------------------------------------------


def test_each_user_sees_their_role(client, org):
    assert client.get("/api/organisation", headers=org["admin"]).json()["role"] == "admin"
    clerk = client.get("/api/organisation", headers=org["clerk"]).json()
    assert clerk["status"] == "ready" and clerk["role"] == "clerk"
    assert clerk["organisation"]["id"] == org["company"]["id"]


# ---- What a Finance Clerk cannot do ------------------------------------------------


@pytest.mark.parametrize("method,path", [
    ("get", "/api/organisation/overview"),
    ("get", "/api/thresholds"),
    ("get", "/api/organisation/members"),
])
def test_clerk_cannot_see_confidential_or_admin_pages(client, org, method, path):
    response = getattr(client, method)(path, headers=org["clerk"])
    assert response.status_code == 403
    assert "CEO / Admin" in response.json()["detail"]


def test_clerk_cannot_view_the_dashboard_or_scores(client, org):
    p = org["period"]["id"]
    assert client.get(_url(org, f"/dashboard/{p}"), headers=org["clerk"]).status_code == 403
    assert client.get(_url(org, f"/indicators/{p}"), headers=org["clerk"]).status_code == 403


def test_clerk_cannot_delete_or_change_settings_or_manage_users(client, org):
    p = org["period"]["id"]
    assert client.delete(_url(org, f"/reporting-periods/{p}"), params={"confirm_label": "FY2025"},
                         headers=org["clerk"]).status_code == 403
    assert client.put(_url(org), json={"name": "Renamed"}, headers=org["clerk"]).status_code == 403
    assert client.post("/api/organisation/invitations",
                       json={"email": "x@example.com", "role": "admin"},
                       headers=org["clerk"]).status_code == 403
    assert client.patch(f"/api/organisation/members/{org['member_id']}",
                        json={"role": "admin"}, headers=org["clerk"]).status_code == 403
    # Nothing was changed.
    assert client.get(_url(org, "/reporting-periods"), headers=org["admin"]).json()
    assert client.get(_url(org), headers=org["admin"]).json()["name"] == "CrystalCorps"


def test_clerk_cannot_set_up_a_second_organisation(client, org):
    assert client.post("/api/organisation", json={"name": "Side business"},
                       headers=org["clerk"]).status_code == 409


# ---- What a Finance Clerk can do -----------------------------------------------------


def test_clerk_maintains_periods_and_records(client, org):
    clerk = org["clerk"]
    assert client.get(_url(org), headers=clerk).status_code == 200
    assert client.get(_url(org, "/reporting-periods"), headers=clerk).status_code == 200
    created = client.post(_url(org, "/reporting-periods"), json={
        "label": "FY2026", "period_start": "2026-01-01", "period_end": "2026-12-31"},
        headers=clerk)
    assert created.status_code == 201
    updated = client.put(_url(org, f"/reporting-periods/{created.json()['id']}"), json={
        "label": "FY2026", "period_start": "2026-01-01", "period_end": "2026-12-31"},
        headers=clerk)
    assert updated.status_code == 200

    records = client.get(_url(org, "/financial-records"), headers=clerk)
    assert records.status_code == 200 and len(records.json()) == 1
    new = client.post(_url(org, "/financial-records"),
                      json=as_request_payload(SOUND_COMPANY, created.json()["id"]), headers=clerk)
    assert new.status_code == 201
    correction = as_request_payload(SOUND_COMPANY, created.json()["id"])
    correction.pop("reporting_period_id")
    assert client.put(f"/api/financial-records/{new.json()['id']}", json=correction,
                      headers=clerk).status_code == 200


def test_clerk_imports_a_trial_balance_and_views_statements(client, org):
    clerk = org["clerk"]
    assert client.post("/api/trial-balance/preview", json={"lines": sample_payload()},
                       headers=clerk).status_code == 200
    record = client.post(_url(org, "/trial-balance"),
                         json={"reporting_period_id": org["period"]["id"],
                               "lines": sample_payload()}, headers=clerk)
    assert record.status_code == 201
    statements = client.get(f"/api/financial-records/{record.json()['id']}/trial-balance",
                            headers=clerk)
    assert statements.status_code == 200
    assert statements.json()["derivation"]["figures"]["net_profit"]["value"] is not None


# ---- What the CEO / Admin can do ------------------------------------------------------


def test_admin_has_full_access(client, org):
    admin, p = org["admin"], org["period"]["id"]
    assert client.get(_url(org, f"/dashboard/{p}"), headers=admin).status_code == 200
    assert client.get("/api/organisation/overview", headers=admin).status_code == 200
    assert client.get("/api/thresholds", headers=admin).status_code == 200
    assert client.put(_url(org), json={"name": "CrystalCorps Sdn Bhd"},
                      headers=admin).status_code == 200
    assert client.delete(_url(org, f"/reporting-periods/{p}"), params={"confirm_label": "FY2025"},
                         headers=admin).status_code == 204


def test_promoting_a_clerk_takes_effect_at_once(client, org):
    p = org["period"]["id"]
    assert client.get(_url(org, f"/dashboard/{p}"), headers=org["clerk"]).status_code == 403
    client.patch(f"/api/organisation/members/{org['member_id']}", json={"role": "admin"},
                 headers=org["admin"])
    assert client.get(_url(org, f"/dashboard/{p}"), headers=org["clerk"]).status_code == 200


# ---- Users and roles ---------------------------------------------------------------------


def test_members_are_listed_with_roles(client, org):
    members = client.get("/api/organisation/members", headers=org["admin"]).json()
    assert {(m["email"], m["role"], m["status"]) for m in members} == {
        ("owner@example.com", "admin", "active"), ("clerk@example.com", "clerk", "active")}
    owner = next(m for m in members if m["role"] == "admin")
    assert owner["is_you"] and owner["is_owner"]


def test_the_organisation_keeps_its_owner_and_an_admin(client, org):
    members = client.get("/api/organisation/members", headers=org["admin"]).json()
    owner = next(m for m in members if m["is_owner"])
    assert client.patch(f"/api/organisation/members/{owner['id']}", json={"role": "clerk"},
                        headers=org["admin"]).status_code == 409
    assert client.delete(f"/api/organisation/members/{owner['id']}",
                         headers=org["admin"]).status_code == 409


def test_removing_a_member_ends_access_but_keeps_the_data(client, org):
    assert client.delete(f"/api/organisation/members/{org['member_id']}",
                         headers=org["admin"]).status_code == 204
    assert client.get("/api/organisation", headers=org["clerk"]).json()["status"] == \
        "setup_required"
    assert client.get(_url(org, "/financial-records"), headers=org["clerk"]).status_code == 404
    assert len(client.get(_url(org, "/financial-records"), headers=org["admin"]).json()) == 1


def test_members_of_another_organisation_are_isolated(client, org):
    outsider = _register(client, "outsider@example.com")
    client.post("/api/organisation", json={"name": "Elsewhere"}, headers=outsider)
    assert client.get(_url(org, "/reporting-periods"), headers=outsider).status_code == 404
    assert client.get(f"/api/financial-records/{org['record']['id']}/trial-balance",
                      headers=outsider).status_code == 404
    assert client.patch(f"/api/organisation/members/{org['member_id']}",
                        json={"role": "admin"}, headers=outsider).status_code == 404
