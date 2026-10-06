# Simulation — extension point for FYP2

**Nothing in this directory is implemented.** It exists to mark where the FYP2
distress simulation will be added, and to record the interface it will use, so
that the boundary between the two stages is explicit rather than implied.

## What FYP2 will add here

| Module | Purpose |
|---|---|
| `propagation` | Propagate the four drivers through a simplified financial model: income statement → receivables and working capital → retained earnings and equity → cash movement → selected balance-sheet items → accounting identity verification. |
| `driver_impact` | Change one driver while the others stay at baseline, and report the model-based impact. |
| `reverse_stress` | Limited reverse stress analysis: one driver, one threshold, a restricted search range, interval halving to an approximate breach point. |

The four drivers will be revenue growth, gross profit margin, operating
expenses and days sales outstanding.

## Why FYP1 needs no change to accommodate it

The calculation engine takes a plain `FinancialInputs` model, never a database
row:

```python
# backend/app/services/assessment_service.py
def assess_financial_inputs(db, data: FinancialInputs, previous_values=None) -> AssessmentOutput
```

The simulation will build a *projected* `FinancialInputs` and pass it through
this same function, so the simulated position is assessed by exactly the engine
that assesses the reported one. No indicator formula, scoring rule or
threshold is duplicated for the simulated case.

`FinancialInputs` is frozen, so a scenario is produced with
`baseline.model_copy(update={...})` rather than by mutating the baseline.

## Deliberately out of scope, in FYP1 and FYP2 alike

* No automatic borrowing or financing adjustment. A projected cash shortfall is
  displayed and the user warned; no debt is drawn, no interest is added, and
  the projection is not adjusted.
* No optimisation across several drivers at once.
* No claim that a simulated breach predicts real-world business failure.
