"""Integration tests for user data isolation.

A user must not be able to reach another user's company or financial data,
even when the identifier is known.
"""

import pytest


@pytest.fixture
def second_user_headers(client):
    client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "full_name": "Other", "password": "another-password"},
    )
    token = client.post(
        "/api/auth/login",
        json={"email": "other@example.com", "password": "another-password"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_company(client, headers, name="Acme Trading"):
    return client.post("/api/companies", json={"name": name}, headers=headers).json()


def test_company_creation_and_listing(client, auth_headers):
    created = _create_company(client, auth_headers)
    assert created["name"] == "Acme Trading"

    listed = client.get("/api/companies", headers=auth_headers).json()
    assert len(listed) == 1


def test_a_user_sees_only_their_own_companies(client, auth_headers, second_user_headers):
    _create_company(client, auth_headers, "Owner Company")
    _create_company(client, second_user_headers, "Other Company")

    owner_list = client.get("/api/companies", headers=auth_headers).json()
    assert [company["name"] for company in owner_list] == ["Owner Company"]


def test_another_users_company_is_not_readable(client, auth_headers, second_user_headers):
    company = _create_company(client, auth_headers)
    response = client.get(f"/api/companies/{company['id']}", headers=second_user_headers)
    assert response.status_code == 404


def test_another_users_company_is_not_editable(client, auth_headers, second_user_headers):
    company = _create_company(client, auth_headers)
    response = client.put(
        f"/api/companies/{company['id']}",
        json={"name": "Hijacked"},
        headers=second_user_headers,
    )
    assert response.status_code == 404


def test_another_users_company_cannot_receive_reporting_periods(
    client, auth_headers, second_user_headers
):
    company = _create_company(client, auth_headers)
    response = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "FY2025", "period_start": "2025-01-01", "period_end": "2025-12-31"},
        headers=second_user_headers,
    )
    assert response.status_code == 404


def test_duplicate_reporting_period_label_is_rejected(client, auth_headers):
    company = _create_company(client, auth_headers)
    payload = {"label": "FY2025", "period_start": "2025-01-01", "period_end": "2025-12-31"}
    first = client.post(
        f"/api/companies/{company['id']}/reporting-periods", json=payload, headers=auth_headers
    )
    second = client.post(
        f"/api/companies/{company['id']}/reporting-periods", json=payload, headers=auth_headers
    )
    assert first.status_code == 201
    assert second.status_code == 409


def test_reporting_period_ending_before_it_starts_is_rejected(client, auth_headers):
    company = _create_company(client, auth_headers)
    response = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "Bad", "period_start": "2025-12-31", "period_end": "2025-01-01"},
        headers=auth_headers,
    )
    assert response.status_code == 422
