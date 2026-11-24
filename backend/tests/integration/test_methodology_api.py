"""API tests for scoring methodology 2.0: benchmark, robustness and periods."""

import pytest

from tests.fixtures.financial_data import SOUND_COMPANY, as_request_payload


def _company(client, auth_headers, period_end="2025-12-31"):
    company = client.post(
        "/api/companies", json={"name": "Acme Trading"}, headers=auth_headers
    ).json()
    period = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "FY2025", "period_start": "2025-01-01", "period_end": period_end},
        headers=auth_headers,
    ).json()
    return company, period


def _dashboard(client, auth_headers, company, period):
    response = client.get(
        f"/api/companies/{company['id']}/dashboard/{period['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    return response.json()


def _enter(client, auth_headers, company, period, **changes):
    payload = as_request_payload(SOUND_COMPANY.model_copy(update=changes), period["id"])
    response = client.post(
        f"/api/companies/{company['id']}/financial-records", json=payload, headers=auth_headers
    )
    assert response.status_code == 201
    return response.json()


def test_retained_earnings_are_stored_and_returned(client, auth_headers):
    company, period = _company(client, auth_headers)
    record = _enter(client, auth_headers, company, period, retained_earnings=-25_000)
    assert record["retained_earnings"] == pytest.approx(-25_000)


def test_retained_earnings_are_optional(client, auth_headers):
    company, period = _company(client, auth_headers)
    record = _enter(client, auth_headers, company, period)
    assert record["retained_earnings"] is None


def test_dashboard_reports_benchmark_unavailable_without_retained_earnings(
    client, auth_headers
):
    company, period = _company(client, auth_headers)
    _enter(client, auth_headers, company, period)
    benchmark = _dashboard(client, auth_headers, company, period)["assessment"]["benchmark"]
    assert benchmark["available"] is False
    assert benchmark["value"] is None
    assert benchmark["missing_inputs"] == ["retained_earnings"]


def test_dashboard_reports_the_benchmark_separately_from_the_score(client, auth_headers):
    company, period = _company(client, auth_headers)
    _enter(client, auth_headers, company, period, retained_earnings=200_000)
    assessment = _dashboard(client, auth_headers, company, period)["assessment"]
    assert assessment["benchmark"]["available"] is True
    assert assessment["benchmark"]["distress_cutoff"] == pytest.approx(1.10)
    assert assessment["benchmark"]["value"] > 0

    # The benchmark does not move the health score: same figures without it.
    # (A second 365-day period of the same organisation: an account has one SME.)
    period2 = client.post(
        f"/api/companies/{company['id']}/reporting-periods",
        json={"label": "FY2023", "period_start": "2023-01-01", "period_end": "2023-12-31"},
        headers=auth_headers,
    ).json()
    _enter(client, auth_headers, company, period2)
    other = _dashboard(client, auth_headers, company, period2)["assessment"]
    assert other["overall_score"] == assessment["overall_score"]


def test_dashboard_includes_robustness_weights_and_version(client, auth_headers):
    company, period = _company(client, auth_headers)
    _enter(client, auth_headers, company, period)
    assessment = _dashboard(client, auth_headers, company, period)["assessment"]

    assert assessment["methodology_version"] == "2.0"
    assert assessment["period_days"] == 365
    assert assessment["scored_indicator_count"] == 10
    assert assessment["total_indicator_count"] == 10
    robustness = assessment["robustness"]
    assert robustness["arithmetic_score"] == assessment["overall_score"]
    assert robustness["geometric_score"] <= robustness["arithmetic_score"]
    assert robustness["weakest_category"] in {
        "liquidity", "profitability", "solvency", "efficiency"
    }
    weights = [item["effective_weight"] for item in assessment["indicators"]]
    assert sum(weights) == pytest.approx(1.0)
    threshold = assessment["indicators"][0]["threshold"]
    assert threshold["floor_value"] is not None
    assert threshold["target_value"] is not None
    assert threshold["basis"]


def test_short_period_is_scaled_and_flagged(client, auth_headers):
    company, period = _company(client, auth_headers, period_end="2025-03-31")
    _enter(client, auth_headers, company, period)
    assessment = _dashboard(client, auth_headers, company, period)["assessment"]

    assert assessment["period_days"] == 90
    dso = next(
        item for item in assessment["indicators"] if item["code"] == "days_sales_outstanding"
    )
    assert dso["value"] == pytest.approx(90_000 / 1_000_000 * 90, abs=1e-3)
    assert any("90 days" in note for note in assessment["data_quality_notes"])


def test_thresholds_endpoint_lists_all_four_reference_points(client, auth_headers):
    _company(client, auth_headers)  # thresholds are visible to a CEO / Admin
    rows = client.get("/api/thresholds", headers=auth_headers).json()
    current = next(row for row in rows if row["indicator_code"] == "current_ratio")
    assert current["floor_value"] == pytest.approx(0.0)
    assert current["distress_threshold"] == pytest.approx(1.0)
    assert current["concern_threshold"] == pytest.approx(1.5)
    assert current["target_value"] == pytest.approx(2.0)
