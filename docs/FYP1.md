# FYP1 — scope and completion

## The boundary

FYP1 establishes the architecture, database, authentication, financial data
processing, financial health assessment, dashboard, tests, documentation and
deployment setup. FYP2 extends it with simulation and explanation.

The boundary is kept honest by one rule: **no FYP2 feature is scaffolded with
behaviour**. `simulation/` and `llm/` hold documentation and nothing else.
There is no endpoint that returns an invented simulated figure, and no module
that returns a placeholder explanation.

## Completion checklist

| Requirement | Status |
|---|---|
| User can register and log in | Implemented |
| User can create and manage an SME | Implemented |
| User can enter financial data | Implemented |
| Financial data is validated | Implemented |
| Reporting periods are supported | Implemented |
| The ten indicators are calculated | Implemented |
| Thresholds are applied | Implemented |
| Each indicator receives a 0–100 score | Implemented |
| Category scores are calculated | Implemented |
| Overall financial health score is calculated | Implemented |
| Sound/Vulnerable/Distressed classification is shown | Implemented |
| Indicators requiring attention are identified | Implemented |
| Dashboard displays results | Implemented |
| Historical reporting periods can be viewed | Implemented |
| Database works | Implemented, migrations applied through Alembic |
| REST API works | Implemented, documented at `/api/docs` |
| Authentication works | Implemented |
| Tests exist and pass | 100 backend, 11 frontend |
| Docker setup exists | Written; not built in this environment |
| Documentation exists | This directory and the README |
| Repository is organised | Four logical commits on `main` |

## How FYP2 attaches

The single decision that makes FYP2 an extension rather than a rewrite is the
signature of the engine:

```python
calculate_indicators(data: FinancialInputs) -> list[CalculatedIndicator]
assess_financial_inputs(db, data: FinancialInputs, previous_values) -> AssessmentOutput
```

`FinancialInputs` is a frozen Pydantic model, not an ORM row. FYP1 loads a
stored record and maps it in. FYP2 will propagate the four drivers through the
simplified financial model, produce a projected `FinancialInputs`, and pass it
through the same two functions. The simulated position is therefore assessed by
exactly the engine that assesses the reported one, with no duplicated formula
and no second scoring rule to keep in step.

Had the engine taken a `FinancialRecord` instead, FYP2 would have had to write
provisional rows to the database or fork the engine. Neither is necessary.
