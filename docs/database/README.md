# Database documentation

See `database/README.md` at the repository root for the schema overview, and
`backend/alembic/versions/` for the migrations themselves.

## Entity relationships

```
users
  └─< companies                 owner_id → users.id
       └─< reporting_periods     company_id → companies.id
            └─< financial_records  reporting_period_id → reporting_periods.id
                 ├─< indicator_results
                 └─< financial_health_scores

threshold_configurations        standalone; one row per indicator
```

Every delete cascades down the ownership chain, so removing a user removes
their data entirely.

## Constraints

| Constraint | Purpose |
|---|---|
| `users.email` unique | One account per email address |
| `uq_period_company_label` | A company cannot have two periods with the same label |
| `uq_record_period_revision` | Revision numbers are unique within a period |
| `threshold_configurations.indicator_code` unique | One active configuration per indicator |

## Why thresholds are a table

Three reasons: values can be revised without changing code; the documented
source travels with the value and can be shown to the user; and a threshold the
application does not recognise is ignored rather than allowed to break an
assessment.
