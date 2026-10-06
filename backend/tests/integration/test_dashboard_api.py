"""Integration tests for financial records, indicators and the dashboard."""

import pytest

from tests.fixtures.financial_data import (
    DISTRESSED_COMPANY,
    SOUND_COMPANY,
    as_request_payload,
)


@pytest.fixture
def company_with_period(client, auth_headers):
    """A company with one reporting period, ready for a financial record."""
    company = client.post(
        "/api/companies", json={"name": "Acme Trading"}, headers=auth_headers
    ).json()
    period = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "FY2025", "period_start": "2025-01-01", "period_end": "2025-12-31"},
        headers=auth_headers,
    ).json()
    return company, period


def test_financial_record_is_created(client, auth_headers, company_with_period):
    company, period = company_with_period
    response = client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, period["id"]),
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["accounting_identity_ok"] is True


def test_record_failing_the_accounting_identity_is_rejected(
    client, auth_headers, company_with_period
):
    company, period = company_with_period
    broken = SOUND_COMPANY.model_copy(update={"total_assets": 900_000})
    response = client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(broken, period["id"]),
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "errors" in response.json()["detail"]


def test_second_record_for_the_same_period_is_rejected(
    client, auth_headers, company_with_period
):
    company, period = company_with_period
    payload = as_request_payload(SOUND_COMPANY, period["id"])
    client.post(
        f"/api/companies/{company['id']}/financial-records", json=payload, headers=auth_headers
    )
    second = client.post(
        f"/api/companies/{company['id']}/financial-records", json=payload, headers=auth_headers
    )
    assert second.status_code == 409


def test_correction_creates_a_new_revision(client, auth_headers, company_with_period):
    company, period = company_with_period
    created = client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, period["id"]),
        headers=auth_headers,
    ).json()

    corrected = SOUND_COMPANY.model_copy(update={"net_profit": 130_000})
    response = client.put(
        f"/api/financial-records/{created['id']}",
        json=corrected.model_dump(),
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["is_current"] is True


def test_indicators_endpoint_returns_all_ten(client, auth_headers, company_with_period):
    company, period = company_with_period
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, period["id"]),
        headers=auth_headers,
    )
    response = client.get(
        f"/api/companies/{company['id']}/indicators/{period['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["indicators"]) == 10
    assert len(body["category_scores"]) == 4


def test_indicator_carries_its_threshold_source(client, auth_headers, company_with_period):
    company, period = company_with_period
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, period["id"]),
        headers=auth_headers,
    )
    body = client.get(
        f"/api/companies/{company['id']}/indicators/{period['id']}", headers=auth_headers
    ).json()
    current_ratio = next(
        item for item in body["indicators"] if item["code"] == "current_ratio"
    )
    assert current_ratio["threshold"]["source_reference"]


def test_sound_company_is_classified_sound(client, auth_headers, company_with_period):
    company, period = company_with_period
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, period["id"]),
        headers=auth_headers,
    )
    body = client.get(
        f"/api/companies/{company['id']}/indicators/{period['id']}", headers=auth_headers
    ).json()
    assert body["classification"] == "sound"


def test_distressed_company_is_not_classified_sound(client, auth_headers, company_with_period):
    company, period = company_with_period
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(DISTRESSED_COMPANY, period["id"]),
        headers=auth_headers,
    )
    body = client.get(
        f"/api/companies/{company['id']}/indicators/{period['id']}", headers=auth_headers
    ).json()
    assert body["classification"] != "sound"
    assert any(item["reason"] for item in body["attention"])


def test_indicators_without_a_record_report_not_found(
    client, auth_headers, company_with_period
):
    company, period = company_with_period
    response = client.get(
        f"/api/companies/{company['id']}/indicators/{period['id']}", headers=auth_headers
    )
    assert response.status_code == 404


def test_dashboard_returns_assessment_summary_and_trend(
    client, auth_headers, company_with_period
):
    company, period = company_with_period
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, period["id"]),
        headers=auth_headers,
    )
    response = client.get(
        f"/api/companies/{company['id']}/dashboard/{period['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["financial_summary"]["gross_profit"] == pytest.approx(400_000)
    assert len(body["score_trend"]) == 1


def test_dashboard_trend_spans_multiple_periods(client, auth_headers, company_with_period):
    company, period = company_with_period
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(DISTRESSED_COMPANY, period["id"]),
        headers=auth_headers,
    )
    later = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "FY2026", "period_start": "2026-01-01", "period_end": "2026-12-31"},
        headers=auth_headers,
    ).json()
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, later["id"]),
        headers=auth_headers,
    )

    body = client.get(
        f"/api/companies/{company['id']}/dashboard/{later['id']}", headers=auth_headers
    ).json()
    assert len(body["score_trend"]) == 2
    assert [point["period_label"] for point in body["score_trend"]] == ["FY2025", "FY2026"]


def test_reporting_period_change_is_reported(client, auth_headers, company_with_period):
    company, period = company_with_period
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(SOUND_COMPANY, period["id"]),
        headers=auth_headers,
    )
    later = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "FY2026", "period_start": "2026-01-01", "period_end": "2026-12-31"},
        headers=auth_headers,
    ).json()
    client.post(
        f"/api/companies/{company['id']}/financial-records",
        json=as_request_payload(DISTRESSED_COMPANY, later["id"]),
        headers=auth_headers,
    )

    body = client.get(
        f"/api/companies/{company['id']}/indicators/{later['id']}", headers=auth_headers
    ).json()
    current_ratio = next(
        item for item in body["indicators"] if item["code"] == "current_ratio"
    )
    assert current_ratio["change"]["previous_value"] == pytest.approx(2.5)
    assert current_ratio["change"]["is_unfavourable"] is True


def test_dashboard_requires_authentication(client, company_with_period):
    company, period = company_with_period
    assert client.get(f"/api/companies/{company['id']}/dashboard/{period['id']}").status_code == 401


def test_thresholds_endpoint_lists_ten_indicators(client, auth_headers):
    response = client.get("/api/thresholds", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 10
