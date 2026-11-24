"""Sensitivity analysis of the financial health score.

Follows step 7 of the OECD/JRC (2008) composite-indicator framework and the
approach of Saisana, Saltelli and Tarantola (2005): change one modelling
choice at a time and record how the overall score and classification move.

Scenario groups:

* thresholds_all   every indicator's thresholds moved by -20%, -10%, +10%, +20%
* threshold_one    one indicator's thresholds moved by +/-20%, the rest unchanged
* weights          equal indicator weights; each category weighted double
* aggregation      geometric instead of arithmetic mean
* missing          each indicator in turn treated as not applicable

A threshold of zero cannot be scaled by a percentage, so it is moved by the
same percentage of the indicator's concern-distress span instead. The floor
and target move with the thresholds, keeping their distances in proportion to
the span. Any perturbed configuration whose reference points are no longer
strictly ordered is skipped and recorded as such.

Stability under these changes shows the result does not hinge on one
arbitrary choice. It is not evidence that the score measures financial health
correctly; that needs comparison against real outcomes.

Usage (inside the backend container):

    python -m app.analysis.sensitivity --from-db --output-dir /tmp/sensitivity
    python -m app.analysis.sensitivity --input companies.json --output-dir out

The input JSON is a list of {"label": ..., "inputs": {FinancialInputs fields}}.
"""

import argparse
import csv
import json
from dataclasses import dataclass, replace
from pathlib import Path

from app.models.enums import IndicatorCategory, IndicatorCode
from app.schemas.financial_inputs import FinancialInputs
from app.services.financial_calculation_service import calculate_indicators
from app.services.scoring_service import (
    METHODOLOGY_VERSION,
    InvalidThresholdError,
    ScoredIndicator,
    ThresholdSetting,
    calculate_category_scores,
    calculate_geometric_overall_score,
    calculate_overall_score,
    classify,
    reference_points_for,
    score_indicators,
)

THRESHOLD_CHANGES = (-0.20, -0.10, 0.10, 0.20)
ONE_AT_A_TIME_CHANGES = (-0.20, 0.20)
ZERO_TOLERANCE = 1e-9


@dataclass(frozen=True)
class ScenarioResult:
    dataset: str
    group: str
    scenario: str
    overall_score: float | None
    classification: str
    change_from_baseline: float | None
    classification_changed: bool
    note: str = ""


def _move(value: float, change: float, span: float) -> float:
    """Move one threshold by a proportion of itself, or of the span at zero."""
    if abs(value) < ZERO_TOLERANCE:
        return value + change * span
    return value * (1 + change)


def perturb_threshold(threshold: ThresholdSetting, change: float) -> ThresholdSetting:
    """Move concern and distress by ``change`` and carry floor and target along.

    Raises InvalidThresholdError when the result is no longer ordered.
    """
    points = reference_points_for(threshold)
    span = abs(points.concern - points.distress)
    concern = _move(points.concern, change, span)
    distress = _move(points.distress, change, span)
    new_span = abs(concern - distress)
    if new_span < ZERO_TOLERANCE:
        raise InvalidThresholdError("concern and distress coincide after the change")
    scale = new_span / span
    sign = 1.0 if (points.target - points.concern) > 0 else -1.0
    perturbed = replace(
        threshold,
        concern_threshold=concern,
        distress_threshold=distress,
        target_value=concern + sign * abs(points.target - points.concern) * scale,
        floor_value=distress - sign * abs(points.distress - points.floor) * scale,
    )
    reference_points_for(perturbed)  # validates ordering
    return perturbed


def _weighted_overall(
    category_scores: dict[IndicatorCategory, float | None],
    weights: dict[IndicatorCategory, float],
) -> float | None:
    applicable = {k: v for k, v in category_scores.items() if v is not None}
    if not applicable:
        return None
    total_weight = sum(weights[k] for k in applicable)
    return round(sum(weights[k] * v for k, v in applicable.items()) / total_weight, 2)


def _equal_indicator_overall(scored: list[ScoredIndicator]) -> float | None:
    scores = [item.score for item in scored if item.score is not None]
    return round(sum(scores) / len(scores), 2) if scores else None


def analyse(
    label: str, data: FinancialInputs, thresholds: dict[IndicatorCode, ThresholdSetting]
) -> list[ScenarioResult]:
    """Run every scenario for one company-period."""
    indicators = calculate_indicators(data)
    base_scored = score_indicators(indicators, thresholds)
    base_categories = calculate_category_scores(base_scored)
    baseline = calculate_overall_score(base_categories)
    base_class = classify(baseline)

    results: list[ScenarioResult] = []

    def record(group: str, scenario: str, overall: float | None, note: str = "") -> None:
        classification = classify(overall)
        results.append(
            ScenarioResult(
                dataset=label,
                group=group,
                scenario=scenario,
                overall_score=overall,
                classification=classification.value,
                change_from_baseline=None
                if overall is None or baseline is None
                else round(overall - baseline, 2),
                classification_changed=classification is not base_class,
                note=note,
            )
        )

    def score_with(settings: dict[IndicatorCode, ThresholdSetting]) -> float | None:
        return calculate_overall_score(
            calculate_category_scores(score_indicators(indicators, settings))
        )

    record("baseline", "baseline", baseline)

    for change in THRESHOLD_CHANGES:
        name = f"all thresholds {change:+.0%}"
        try:
            settings = {code: perturb_threshold(t, change) for code, t in thresholds.items()}
        except InvalidThresholdError as error:
            record("thresholds_all", name, None, f"skipped: {error}")
            continue
        record("thresholds_all", name, score_with(settings))

    for code, threshold in thresholds.items():
        for change in ONE_AT_A_TIME_CHANGES:
            name = f"{code.value} {change:+.0%}"
            try:
                settings = {**thresholds, code: perturb_threshold(threshold, change)}
            except InvalidThresholdError as error:
                record("threshold_one", name, None, f"skipped: {error}")
                continue
            record("threshold_one", name, score_with(settings))

    record("weights", "equal indicator weights", _equal_indicator_overall(base_scored))
    for category in IndicatorCategory:
        weights = {k: (2.0 if k is category else 1.0) for k in IndicatorCategory}
        record(
            "weights",
            f"{category.value} weighted double",
            _weighted_overall(base_categories, weights),
        )

    record("aggregation", "geometric mean", calculate_geometric_overall_score(base_categories))

    for code in thresholds:
        reduced = [
            replace(item, score=None) if item.code is code else item for item in base_scored
        ]
        record(
            "missing",
            f"without {code.value}",
            calculate_overall_score(calculate_category_scores(reduced)),
        )

    return results


def summarise(results: list[ScenarioResult]) -> dict:
    """Range, classification changes and most influential factors per dataset."""
    summary: dict[str, dict] = {}
    for label in dict.fromkeys(r.dataset for r in results):
        rows = [r for r in results if r.dataset == label]
        baseline = next(r for r in rows if r.group == "baseline")
        scored = [r for r in rows if r.overall_score is not None and r.group != "baseline"]
        changes = [r for r in scored if r.classification_changed]
        influential = sorted(
            scored, key=lambda r: abs(r.change_from_baseline or 0), reverse=True
        )[:5]
        scores = [r.overall_score for r in scored] + (
            [baseline.overall_score] if baseline.overall_score is not None else []
        )
        summary[label] = {
            "baseline_score": baseline.overall_score,
            "baseline_classification": baseline.classification,
            "scenarios_run": len(scored),
            "scenarios_skipped": sum(1 for r in rows if r.note.startswith("skipped")),
            "minimum_score": min(scores) if scores else None,
            "maximum_score": max(scores) if scores else None,
            "classification_changes": len(changes),
            "scenarios_changing_classification": [r.scenario for r in changes],
            "most_influential": [
                {"scenario": r.scenario, "change": r.change_from_baseline} for r in influential
            ],
            "stability": (
                "stable: no scenario changed the classification"
                if not changes
                else f"{len(changes)} of {len(scored)} scenarios changed the classification"
            ),
        }
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "caveat": "Stability under these changes is not evidence that the score is "
        "valid; that requires comparison with actual financial outcomes.",
        "datasets": summary,
    }


def write_outputs(results: list[ScenarioResult], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "sensitivity_scenarios.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["dataset", "group", "scenario", "overall_score", "classification",
             "change_from_baseline", "classification_changed", "note"]
        )
        for r in results:
            writer.writerow(
                [r.dataset, r.group, r.scenario, r.overall_score, r.classification,
                 r.change_from_baseline, r.classification_changed, r.note]
            )
    json_path = output_dir / "sensitivity_summary.json"
    json_path.write_text(json.dumps(summarise(results), indent=2), encoding="utf-8")
    return csv_path, json_path


def _datasets_from_db() -> list[tuple[str, FinancialInputs]]:
    # Imported here so the pure analysis functions need no database.
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.financial_record import FinancialRecord
    from app.utils.presenters import record_to_inputs

    with SessionLocal() as db:
        records = db.execute(
            select(FinancialRecord).where(FinancialRecord.is_current.is_(True))
        ).scalars()
        return [
            (
                f"{record.reporting_period.company.name} {record.reporting_period.label}",
                record_to_inputs(record),
            )
            for record in records
        ]


def _thresholds_from_db() -> dict[IndicatorCode, ThresholdSetting]:
    from app.core.database import SessionLocal
    from app.services.threshold_service import load_threshold_settings

    with SessionLocal() as db:
        return load_threshold_settings(db)


def _default_thresholds() -> dict[IndicatorCode, ThresholdSetting]:
    from app.services.threshold_service import DEFAULT_THRESHOLDS

    return {
        e["indicator_code"]: ThresholdSetting(
            indicator_code=e["indicator_code"],
            direction=e["direction"],
            concern_threshold=e["concern_threshold"],
            distress_threshold=e["distress_threshold"],
            source_reference=e["source_reference"],
            description=e["description"],
        )
        for e in DEFAULT_THRESHOLDS
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-db", action="store_true", help="every current record")
    source.add_argument("--input", type=Path, help="JSON list of {label, inputs}")
    parser.add_argument("--output-dir", type=Path, default=Path("sensitivity_output"))
    args = parser.parse_args()

    if args.from_db:
        datasets = _datasets_from_db()
        thresholds = _thresholds_from_db()
    else:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        datasets = [(item["label"], FinancialInputs(**item["inputs"])) for item in raw]
        thresholds = _default_thresholds()

    results = [row for label, data in datasets for row in analyse(label, data, thresholds)]
    csv_path, json_path = write_outputs(results, args.output_dir)
    print(f"{len(datasets)} datasets, {len(results)} scenario results")
    print(f"wrote {csv_path} and {json_path}")


if __name__ == "__main__":
    main()
