# Interactive Financial Health Monitoring Dashboard for SMEs

A web application that assesses the financial health of a small or medium-sized
enterprise from its financial statements, and presents the result through an
interactive dashboard.

This repository holds **FYP1**. Distress simulation, driver impact analysis,
reverse stress analysis and the language-model explanation layer are planned
for FYP2 and are **not implemented here**. Where they will attach is marked by
`simulation/` and `llm/`, which contain documentation and no code.

---

## What the system does

A user enters financial statement data for a reporting period. The system then:

1. validates the data, including the accounting identity `Assets = Liabilities + Equity`;
2. calculates ten fixed financial indicators;
3. compares each indicator with its documented concern and distress thresholds;
4. scores each indicator from 0 to 100;
5. averages the applicable indicator scores into four category scores;
6. averages the applicable category scores, equally weighted, into an overall score;
7. classifies the company as Sound, Vulnerable or Distressed;
8. identifies the indicators requiring attention;
9. displays all of this, with the source of every threshold.

### The ten indicators

| Category | Indicators |
|---|---|
| Liquidity | Current ratio, quick ratio |
| Profitability | Gross profit margin, net profit margin, return on assets |
| Solvency | Debt-to-equity ratio, debt ratio, interest coverage ratio |
| Efficiency | Asset turnover, days sales outstanding |

This set is fixed. No statistical procedure selects a subset, and no machine
learning, sector benchmarking, entropy weighting, AHP or TOPSIS is used
anywhere in the implemented system.

### Scoring

The scale is anchored at each indicator's own two thresholds: a value at the
concern threshold scores exactly 60, a value at the distress threshold scores
exactly 40, and the scale continues linearly beyond each, measured in units of
the span between them and clamped to 0–100.

An indicator that cannot be calculated — a zero denominator, or a value the
company does not report — scores `N/A`, never zero, and is excluded from its
category average rather than dragging it down.

| Overall score | Classification |
|---|---|
| 60–100 | Sound |
| 40–59 | Vulnerable |
| 0–39 | Distressed |

### Indicators requiring attention

Attention is determined by two things only: **threshold status** and
**reporting-period change**. Threshold breaches come first (distress before
concern), then indicators that have moved against the enterprise by more than a
configured proportion since the previous period, then the rest. All ten
indicators remain visible; this ordering governs prominence, not selection.

---

## Technology

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic |
| Database | PostgreSQL 16 |
| Frontend | React 18, Vite, Apache ECharts, TanStack Query, React Router |
| Testing | pytest (backend), Vitest (frontend) |
| Deployment | Docker Compose, GitHub Actions |

---

## Project structure

```
backend/
  app/
    api/routes/     auth, companies, financial_records, indicators, dashboard,
                    thresholds, health
    core/           config, security, database
    models/         SQLAlchemy models and the shared enumerations
    schemas/        Pydantic request and response models
    services/       calculation, scoring, thresholds, attention, validation,
                    assessment, authentication
    utils/          presenters and record helpers
  tests/            unit, integration and fixtures
  alembic/          migrations
frontend/
  src/
    charts/         reusable ECharts components
    components/     dashboard pieces
    context/        authentication state
    pages/          routed screens
    services/       API client
database/           schema documentation
docs/               architecture, API, database and testing notes
simulation/         FYP2 extension point (documentation only)
llm/                FYP2 extension point (documentation only)
scripts/            setup and development helpers
```

### One deliberate departure from the proposed structure

The proposed structure included a `repositories/` layer between the services
and the ORM. It was left out: SQLAlchemy's session already abstracts data
access, and a repository over it would add a file per entity that only forwards
calls. Services use the ORM directly, which keeps the code shorter and easier
to follow without losing the separation between the API routes and the
financial logic.

---

## Running the project

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD and JWT_SECRET_KEY.
# Generate a secret with:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up --build
```

| Service | Address |
|---|---|
| Frontend | http://localhost:5173 |
| API documentation | http://localhost:8000/api/docs |
| Health check | http://localhost:8000/api/health |

The backend container applies migrations and seeds the threshold table before
serving, so the application is ready on first start.

### Running locally without Docker

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
python ../scripts/setup/seed_thresholds.py
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

---

## Environment variables

Copy `.env.example` to `.env`. No secret is committed; `.env` is ignored by Git.

| Variable | Purpose |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` | Database connection |
| `DATABASE_URL` | Full SQLAlchemy URL; overrides the parts above when set |
| `JWT_SECRET_KEY` | Signs access tokens. Generate a random value |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime |
| `ENVIRONMENT` | `development` or `production` |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `VITE_API_BASE_URL` | API address the frontend calls |

---

## API

Interactive documentation is generated by FastAPI at `/api/docs`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/auth/register` | Create an account |
| `POST` | `/api/auth/login` | Obtain an access token |
| `POST` | `/api/auth/logout` | Log out (the client discards its token) |
| `GET` | `/api/auth/me` | Current account |
| `POST` `GET` | `/api/companies` | Create and list companies |
| `GET` `PUT` | `/api/companies/{id}` | Read and update a company |
| `POST` `GET` | `/api/companies/{id}/reporting-periods` | Manage reporting periods |
| `POST` `GET` | `/api/companies/{id}/financial-records` | Enter and list financial data |
| `PUT` | `/api/financial-records/{id}` | Store a correction as a new revision |
| `GET` | `/api/companies/{id}/indicators/{period_id}` | Indicators, scores and attention |
| `GET` | `/api/companies/{id}/dashboard/{period_id}` | Full dashboard payload |
| `GET` | `/api/thresholds` | Configured thresholds and their sources |
| `GET` | `/api/health` | Service and database health |

---

## Testing

```bash
cd backend && pytest                 # 100 tests
cd frontend && npm run test -- --run #  11 tests
```

The backend suite runs against in-memory SQLite, so it needs no database
server; the application itself runs against PostgreSQL. Indicator expectations
are computed by hand in `backend/tests/fixtures/financial_data.py`, so the
tests check the implementation against an independent calculation rather than
against its own output.

GitHub Actions runs both suites and the frontend build on every push and pull
request.

---

## Security

Implemented: bcrypt password hashing, JWT authentication, protected routes,
request validation through Pydantic, parameterised queries through the ORM,
per-user data isolation enforced in a shared dependency, configurable CORS,
secrets read from the environment, and a generic error response that logs the
detail rather than returning a stack trace.

This is an academic project. It has not been security-audited and makes no
claim of certification.

---

## Implementation status

### Implemented in FYP1

- [x] Registration, login, logout, JWT authentication, protected routes
- [x] Per-user data isolation
- [x] Company management and reporting periods
- [x] Manual financial data entry with field and cross-field validation
- [x] Accounting identity check, with failing records rejected and the reason returned
- [x] Record revisions, so corrections preserve history
- [x] All ten indicators in a standalone calculation service
- [x] Threshold configuration in the database, with the source of each value
- [x] 0–100 indicator scoring, both directions handled explicitly
- [x] Category scores from applicable indicators only
- [x] Equal-weighted overall score and Sound/Vulnerable/Distressed classification
- [x] Indicators requiring attention, by threshold status and reporting-period change
- [x] Dashboard with score summary, category comparison, indicator status,
      health score trend, attention list, financial summary and the full
      indicator table
- [x] Responsive layout for desktop and tablet, usable at phone width
- [x] 111 automated tests and a CI workflow
- [x] Docker Compose for backend, frontend and PostgreSQL

### Planned for FYP2 — not implemented

- [ ] Distress simulation with four drivers
- [ ] Propagation through a simplified financial model
- [ ] Baseline versus scenario comparison
- [ ] Driver impact analysis
- [ ] Limited reverse stress analysis by interval halving
- [ ] Language-model explanation with numerical grounding validation
- [ ] Expanded evaluation

`simulation/` and `llm/` contain documentation of these extension points and no
code. Nothing in the running system produces a simulated figure or a generated
explanation.

---

## Scope boundaries

The system is a financial health **monitoring** tool, and in FYP2 a
**simulation** tool. It is not a financial advisory system. It does not predict
business failure, does not give financing, investment or restructuring
recommendations, does not perform bookkeeping or transaction management, does
not integrate with accounting software, and does not consolidate multiple
currencies or group companies. Results are model-based and do not establish
real-world causation.

## Licence

MIT. See `LICENSE`.
