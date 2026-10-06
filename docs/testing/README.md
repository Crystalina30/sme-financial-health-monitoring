# Testing

```bash
cd backend && pytest                      # 100 tests
cd frontend && npm run test -- --run      #  11 tests
```

## Approach

Indicator expectations are **computed by hand** in
`backend/tests/fixtures/financial_data.py`, with the arithmetic written out in
the fixture's docstring. The tests therefore check the implementation against an
independent calculation, not against its own output — which is the point of
testing a financial engine.

The backend suite runs against in-memory SQLite, created and dropped per test,
so it needs no database server and tests cannot leak state into one another.
The application runs against PostgreSQL; no raw SQL is used, so the ORM layer
behaves the same against both.

## Coverage

| Area | Tests |
|---|---|
| Indicator calculations | Each of the ten against a hand-computed value |
| Division by zero | Every indicator returns N/A rather than raising |
| Missing data | Absent inventory, no interest expense, negative equity |
| Scoring anchors | 60 at concern, 40 at distress, clamped to 0–100 |
| Scoring direction | Higher-is-better and lower-is-better handled separately |
| Status | Sound, concern, distress, and values exactly at a threshold |
| N/A handling | Not scored as zero; excluded from the category average |
| Aggregation | Category averaging, overall averaging, classification bands |
| Validation | Accounting identity, rounding tolerance, field-level rules |
| Period change | Favourable and unfavourable movement in both directions |
| Attention | Priority order, breach outranking movement, all ten returned |
| Authentication | Registration, duplicate email, login, wrong password, token handling |
| Isolation | Another user's company is unreachable for read, update and nesting |
| API | Record creation, rejection, revisions, indicators, dashboard, trend |
| Frontend | API client token handling and error surfacing, display formatting |

## Not covered

No end-to-end browser test, and no load testing. Both are out of scope for
FYP1 and are noted here rather than implied by their absence.
