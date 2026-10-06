# Architecture

## Layers

```
HTTP request
   │
   ▼
API route            ── validates the request shape, checks ownership
   │                     no financial logic lives here
   ▼
Service              ── calculation, scoring, attention, validation
   │                     no HTTP and no database concerns
   ▼
Model (SQLAlchemy)   ── persistence
```

A route handler contains no formula. A service contains no request or response
object. This is what makes the financial logic testable without a web server
and reusable by FYP2 without a web request.

## The calculation path

```
FinancialRecord (database row)
   │  record_to_inputs()
   ▼
FinancialInputs (frozen Pydantic model)      ← FYP2 will also produce one here
   │  calculate_indicators()
   ▼
list[CalculatedIndicator]       value or None, never a zero standing for N/A
   │  score_indicators()        thresholds loaded from the database
   ▼
list[ScoredIndicator]           score, status and threshold context
   │  calculate_category_scores() → calculate_overall_score() → classify()
   ▼
HealthAssessment
   │  identify_attention()      threshold status + reporting-period change
   ▼
AssessmentOutput → response schemas
```

## Decisions worth defending

**The engine takes a plain input model, never a database row.** This is what
lets the FYP2 simulation feed a projected position through the same engine. See
`docs/FYP1.md`.

**`None` means not applicable; it never means zero.** A quick ratio for a
company that reports no inventory, or interest coverage for a company with no
borrowings, is absent, not bad. Scoring it zero would misstate the category
average. The distinction is carried end to end: `None` in the engine, `null` in
the API, `N/A` with a reason on the dashboard.

**Status and score are computed separately.** Status is a categorical
comparison with the thresholds; score is a continuous position measure. Neither
is derived from the other, so there is no boundary case where a score band and
a status disagree.

**Corrections create revisions.** Updating a financial record marks the old row
superseded and inserts a new one, so an assessment can always be traced to the
figures behind it.

**Ownership is enforced in one place.** Every company lookup goes through the
`get_owned_company` dependency, so isolation cannot be forgotten in a new route.
A company belonging to another user returns 404, not 403, so the API does not
confirm that an identifier exists.

**No repository layer.** SQLAlchemy's session already abstracts data access.
A repository over it would add a file per entity that only forwards calls.
