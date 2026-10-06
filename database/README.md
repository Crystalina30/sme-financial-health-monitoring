# Database

PostgreSQL 16. The schema is managed entirely through Alembic migrations in
`backend/alembic/versions`; the database is never modified by hand.

## Tables

| Table | Purpose |
|---|---|
| `users` | Account records. Only a bcrypt password hash is stored. |
| `companies` | One SME, owned by exactly one user. |
| `reporting_periods` | A financial period for one company. Unique per company by label. |
| `financial_records` | Standardised statement values for one period, versioned by `revision`. |
| `threshold_configurations` | Concern and distress thresholds per indicator, with the documented source of each value. |
| `indicator_results` | Persisted indicator values and scores, so historical assessments stay reproducible. |
| `financial_health_scores` | Persisted category and overall scores for a record. |

## Ownership chain

    User → Company → ReportingPeriod → FinancialRecord

Every API lookup walks this chain from the authenticated user, so a user
cannot reach another user's data by guessing an identifier.

## Revisions

Correcting a financial record does not overwrite it. The existing row is
marked `is_current = false` and a new row is inserted with `revision + 1`, so
an assessment produced earlier can still be traced to the figures behind it.

## Applying migrations

```bash
cd backend
alembic upgrade head
python ../scripts/setup/seed_thresholds.py
```
