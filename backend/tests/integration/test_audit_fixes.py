"""Regression tests for the issues in FYP2_CODEBASE_AUDIT.md.

1. Invitations: single-use, expiring tokens, accepted by the intended,
   signed-in recipient; nothing is claimed by email alone.
5. Stale or concurrent revisions are refused with 409.
6. Non-finite numbers are refused.
7. Who changed what is recorded.
(2, 3 and 4 are covered in the unit tests for the trial balance and validation.)
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.financial_record import FinancialRecord
from app.models.membership import OrganisationInvitation, OrganisationMember
from tests.fixtures.financial_data import SOUND_COMPANY, as_request_payload
from tests.fixtures.trial_balance import sample_payload

PASSWORD = "correct-horse-battery"


def _register(client, email, name="Someone"):
    client.post("/api/auth/register", json={"email": email, "full_name": name, "password": PASSWORD})
    token = client.post("/api/auth/login",
                        json={"email": email, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org(client, auth_headers):
    company = client.post("/api/organisation", json={"name": "CrystalCorps"},
                          headers=auth_headers).json()
    period = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "FY2025", "period_start": "2025-01-01", "period_end": "2025-12-31"},
        headers=auth_headers).json()
    return {"company": company, "period": period, "admin": auth_headers}


def _invite(client, org, email="clerk@example.com", role="clerk"):
    response = client.post("/api/organisation/invitations", json={"email": email, "role": role},
                           headers=org["admin"])
    assert response.status_code == 201, response.text
    return response.json()


def _accept(client, headers, token):
    return client.post("/api/organisation/invitations/accept", json={"token": token},
                       headers=headers)


def _status(client, headers):
    return client.get("/api/organisation", headers=headers).json()


# ---- 1. Invitations -------------------------------------------------------------------


def test_registering_with_an_invited_email_does_not_grant_access(client, org):
    _invite(client, org, "victim@example.com", role="admin")
    impostor = _register(client, "victim@example.com", "Impostor")
    # No token, no access: the invitation is not claimed by email.
    assert _status(client, impostor)["status"] == "setup_required"
    assert client.get(f"/api/companies/{org['company']['id']}",
                      headers=impostor).status_code == 404


def test_the_token_is_shown_once_and_stored_only_as_a_hash(client, db_session, org):
    invitation = _invite(client, org)
    stored = db_session.get(OrganisationInvitation, invitation["id"])
    assert stored.token_hash != invitation["token"]
    assert len(stored.token_hash) == 64
    listed = client.get("/api/organisation/invitations", headers=org["admin"]).json()
    assert "token" not in listed[0]
    assert listed[0]["state"] == "pending"


def test_the_intended_recipient_accepts_explicitly(client, org):
    invitation = _invite(client, org)
    clerk = _register(client, "clerk@example.com")
    assert _status(client, clerk)["status"] == "setup_required"  # nothing automatic
    preview = client.get("/api/organisation/invitations/preview",
                         params={"token": invitation["token"]}, headers=clerk).json()
    assert preview["organisation_name"] == "CrystalCorps" and preview["role"] == "clerk"
    response = _accept(client, clerk, invitation["token"])
    assert response.status_code == 200
    assert response.json()["role"] == "clerk"


def test_a_token_for_another_email_is_refused(client, org):
    invitation = _invite(client, org, "clerk@example.com")
    someone_else = _register(client, "someone@example.com")
    response = _accept(client, someone_else, invitation["token"])
    assert response.status_code == 403
    assert _status(client, someone_else)["status"] == "setup_required"


def test_a_token_cannot_be_replayed(client, org):
    invitation = _invite(client, org)
    clerk = _register(client, "clerk@example.com")
    assert _accept(client, clerk, invitation["token"]).status_code == 200
    assert _accept(client, clerk, invitation["token"]).status_code == 410


def test_an_expired_token_is_refused(client, db_session, org):
    invitation = _invite(client, org)
    row = db_session.get(OrganisationInvitation, invitation["id"])
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    clerk = _register(client, "clerk@example.com")
    response = _accept(client, clerk, invitation["token"])
    assert response.status_code == 410
    assert "expired" in response.json()["detail"]


def test_a_revoked_token_is_refused(client, org):
    invitation = _invite(client, org)
    assert client.delete(f"/api/organisation/invitations/{invitation['id']}",
                         headers=org["admin"]).status_code == 204
    clerk = _register(client, "clerk@example.com")
    assert _accept(client, clerk, invitation["token"]).status_code == 410


def test_a_new_invitation_replaces_the_pending_one(client, org):
    first = _invite(client, org)
    second = _invite(client, org)
    clerk = _register(client, "clerk@example.com")
    assert _accept(client, clerk, first["token"]).status_code == 410
    assert _accept(client, clerk, second["token"]).status_code == 200


def test_an_unknown_token_is_not_found(client, org):
    clerk = _register(client, "clerk@example.com")
    assert _accept(client, clerk, "not-a-real-token").status_code == 404


def test_a_member_of_another_organisation_cannot_accept(client, org):
    invitation = _invite(client, org, "boss@example.com")
    boss = _register(client, "boss@example.com")
    client.post("/api/organisation", json={"name": "Boss Co"}, headers=boss)
    assert _accept(client, boss, invitation["token"]).status_code == 409


def test_a_clerk_cannot_invite(client, org):
    invitation = _invite(client, org)
    clerk = _register(client, "clerk@example.com")
    _accept(client, clerk, invitation["token"])
    assert client.post("/api/organisation/invitations",
                       json={"email": "x@example.com", "role": "admin"},
                       headers=clerk).status_code == 403


def test_another_organisation_cannot_revoke(client, org):
    invitation = _invite(client, org)
    outsider = _register(client, "outsider@example.com")
    client.post("/api/organisation", json={"name": "Elsewhere"}, headers=outsider)
    assert client.delete(f"/api/organisation/invitations/{invitation['id']}",
                         headers=outsider).status_code == 404


def test_existing_members_cannot_be_invited_again(client, org):
    response = client.post("/api/organisation/invitations",
                           json={"email": "owner@example.com", "role": "clerk"},
                           headers=org["admin"])
    assert response.status_code == 409


# ---- 5. Stale and concurrent revisions ---------------------------------------------------


def _record(client, org):
    response = client.post(f"/api/companies/{org['company']['id']}/financial-records",
                           json=as_request_payload(SOUND_COMPANY, org["period"]["id"]),
                           headers=org["admin"])
    assert response.status_code == 201
    return response.json()


def _correct(client, org, record_id, **changes):
    payload = as_request_payload(SOUND_COMPANY.model_copy(update=changes), org["period"]["id"])
    payload.pop("reporting_period_id")
    return client.put(f"/api/financial-records/{record_id}", json=payload, headers=org["admin"])


def test_editing_a_superseded_revision_is_refused(client, org):
    first = _record(client, org)
    assert _correct(client, org, first["id"]).status_code == 200  # revision 2
    stale = _correct(client, org, first["id"])  # someone still looking at revision 1
    assert stale.status_code == 409
    assert "superseded by revision 2" in stale.json()["detail"]


def test_only_one_revision_can_be_current(client, db_session, org):
    first = _record(client, org)
    columns = {c.name for c in FinancialRecord.__table__.columns}
    db_session.add(FinancialRecord(
        reporting_period_id=org["period"]["id"], revision=99, is_current=True,
        **{k: v for k, v in as_request_payload(SOUND_COMPANY, 0).items()
           if k in columns and k != "reporting_period_id"},
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert first["revision"] == 1


def test_a_second_first_record_is_refused_not_a_500(client, org):
    _record(client, org)
    response = client.post(f"/api/companies/{org['company']['id']}/financial-records",
                           json=as_request_payload(SOUND_COMPANY, org["period"]["id"]),
                           headers=org["admin"])
    assert response.status_code == 409


# ---- 6. Non-finite numbers ----------------------------------------------------------------


@pytest.mark.parametrize("value", ["Infinity", "-Infinity", "NaN"])
def test_non_finite_amounts_are_refused(client, org, value):
    body = as_request_payload(SOUND_COMPANY, org["period"]["id"])
    text = __import__("json").dumps(body).replace('"revenue": 1200000.0', f'"revenue": {value}')
    text = text.replace(f'"revenue": {SOUND_COMPANY.revenue}', f'"revenue": {value}')
    response = client.post(f"/api/companies/{org['company']['id']}/financial-records",
                           content=text, headers={**org["admin"], "Content-Type": "application/json"})
    assert response.status_code == 422


def test_non_finite_trial_balance_amounts_are_refused(client, org):
    text = '{"lines": [{"account_name": "Cash", "debit": Infinity, "credit": 0, "category": "cash"}]}'
    response = client.post("/api/trial-balance/preview", content=text,
                           headers={**org["admin"], "Content-Type": "application/json"})
    assert response.status_code == 422


# ---- 7. Audit trail ---------------------------------------------------------------------------


def test_changes_are_attributed_and_logged(client, org):
    invitation = _invite(client, org)
    clerk = _register(client, "clerk@example.com", "Clerk")
    _accept(client, clerk, invitation["token"])
    company_id = org["company"]["id"]

    created = client.post(f"/api/companies/{company_id}/financial-records",
                          json=as_request_payload(SOUND_COMPANY, org["period"]["id"]),
                          headers=clerk).json()
    assert created["created_by_email"] == "clerk@example.com"
    corrected = _correct(client, org, created["id"], revenue=SOUND_COMPANY.revenue + 1_000)
    assert corrected.json()["created_by_email"] == "owner@example.com"
    client.post(f"/api/companies/{company_id}/trial-balance",
                json={"reporting_period_id": org["period"]["id"], "lines": sample_payload()},
                headers=clerk)
    client.delete(f"/api/companies/{company_id}/reporting-periods/{org['period']['id']}",
                  params={"confirm_label": "FY2025"}, headers=org["admin"])

    log = client.get("/api/organisation/audit-log", headers=org["admin"]).json()
    actions = [(e["action"], e["actor_email"]) for e in reversed(log)]
    assert actions == [
        ("organisation.created", "owner@example.com"),
        ("period.created", "owner@example.com"),
        ("invitation.created", "owner@example.com"),
        ("invitation.accepted", "clerk@example.com"),
        ("record.created", "clerk@example.com"),
        ("record.corrected", "owner@example.com"),
        ("trial_balance.imported", "clerk@example.com"),
        ("period.deleted", "owner@example.com"),
    ]
    corrected_event = next(e for e in log if e["action"] == "record.corrected")
    assert corrected_event["detail"]["changed"]["revenue"]["to"] == SOUND_COMPANY.revenue + 1_000
    deleted = next(e for e in log if e["action"] == "period.deleted")
    assert [r["revision"] for r in deleted["detail"]["revisions"]] == [1, 2, 3]
    # Only admins read the log, and nobody can change it.
    assert client.get("/api/organisation/audit-log", headers=clerk).status_code == 403
    assert client.delete("/api/organisation/audit-log", headers=org["admin"]).status_code == 405


def test_deleting_a_period_requires_naming_it(client, org):
    url = f"/api/companies/{org['company']['id']}/reporting-periods/{org['period']['id']}"
    wrong = client.delete(url, params={"confirm_label": "FY2024"}, headers=org["admin"])
    assert wrong.status_code == 422
    assert client.delete(url, headers=org["admin"]).status_code == 422
    assert client.delete(url, params={"confirm_label": "FY2025"},
                         headers=org["admin"]).status_code == 204


def test_stock_confirmations_are_kept_as_evidence(client, org):
    lines = [line for line in sample_payload() if line["account_name"] != "Closing stock"]
    for line in lines:
        if line["account_name"] == "Stock":
            line["debit"] = 0
    lines.append({"account_name": "Closing stock (period-end adjustment: confirmed nil)",
                  "debit": 0, "credit": 0, "category": "cost_of_sales",
                  "source_ref": "Period-end adjustment: no closing stock, confirmed by user"})
    lines.append({"account_name": "Rounding to keep the test balanced", "debit": 0,
                  "credit": 0, "category": "cash"})
    response = client.post(f"/api/companies/{org['company']['id']}/trial-balance",
                           json={"reporting_period_id": org["period"]["id"], "lines": lines},
                           headers=org["admin"])
    assert response.status_code == 201, response.text
    event = client.get("/api/organisation/audit-log", headers=org["admin"]).json()[0]
    assert event["action"] == "trial_balance.imported"
    assert event["detail"]["period_end_adjustments"][0]["account"].startswith("Closing stock")
