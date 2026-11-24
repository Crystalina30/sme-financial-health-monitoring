"""Tests for the sensitivity-analysis research script."""

import json

import pytest

from app.analysis.sensitivity import analyse, perturb_threshold, summarise, write_outputs
from app.models.enums import IndicatorCode
from app.services.scoring_service import ThresholdSetting, reference_points_for
from app.services.threshold_service import DEFAULT_THRESHOLDS
from tests.fixtures.financial_data import SOUND_COMPANY


def _settings():
    return {
        e["indicator_code"]: ThresholdSetting(
            indicator_code=e["indicator_code"],
            direction=e["direction"],
            concern_threshold=e["concern_threshold"],
            distress_threshold=e["distress_threshold"],
            source_reference="",
            description="",
        )
        for e in DEFAULT_THRESHOLDS
    }


@pytest.mark.parametrize("change", [-0.2, -0.1, 0.1, 0.2])
@pytest.mark.parametrize("entry", DEFAULT_THRESHOLDS, ids=lambda e: e["indicator_code"].value)
def test_every_default_threshold_can_be_perturbed_and_stays_ordered(entry, change):
    threshold = _settings()[entry["indicator_code"]]
    perturbed = perturb_threshold(threshold, change)
    reference_points_for(perturbed)  # raises if the ordering broke


def test_percentage_change_scales_nonzero_thresholds():
    current = _settings()[IndicatorCode.CURRENT_RATIO]
    perturbed = perturb_threshold(current, 0.10)
    assert perturbed.concern_threshold == pytest.approx(1.65)
    assert perturbed.distress_threshold == pytest.approx(1.10)


def test_zero_threshold_moves_by_a_share_of_the_span():
    # Net profit margin: distress 0, concern 5, span 5.
    margin = _settings()[IndicatorCode.NET_PROFIT_MARGIN]
    perturbed = perturb_threshold(margin, 0.10)
    assert perturbed.distress_threshold == pytest.approx(0.5)
    assert perturbed.concern_threshold == pytest.approx(5.5)


def test_analysis_runs_every_scenario_and_baseline_matches_the_score():
    results = analyse("Sound", SOUND_COMPANY, _settings())
    groups = {r.group for r in results}
    assert groups == {
        "baseline", "thresholds_all", "threshold_one", "weights", "aggregation", "missing"
    }
    baseline = next(r for r in results if r.group == "baseline")
    assert baseline.change_from_baseline == 0
    # 1 baseline + 4 all + 20 one-at-a-time + 5 weights + 1 aggregation + 10 missing
    assert len(results) == 41


def test_summary_and_files_are_written(tmp_path):
    results = analyse("Sound", SOUND_COMPANY, _settings())
    csv_path, json_path = write_outputs(results, tmp_path)
    assert csv_path.read_text(encoding="utf-8").count("\n") == len(results) + 1
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    sound = summary["datasets"]["Sound"]
    assert sound["minimum_score"] <= sound["baseline_score"] <= sound["maximum_score"]
    assert "not evidence" in summary["caveat"]
    assert summarise(results)["methodology_version"] == "2.0"
