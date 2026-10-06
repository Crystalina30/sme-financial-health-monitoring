# Development helpers

| Script | Purpose |
|---|---|
| `../setup/seed_thresholds.py` | Insert the default threshold rows. Safe to run twice. |

## Common tasks

```bash
# Backend tests
cd backend && pytest

# A new migration after changing a model
cd backend && alembic revision --autogenerate -m "describe the change"
cd backend && alembic upgrade head

# Frontend
cd frontend && npm run dev
cd frontend && npm run test -- --run
cd frontend && npm run build
```
