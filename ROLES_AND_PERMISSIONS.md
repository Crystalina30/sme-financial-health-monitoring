# Roles and Permissions: one SME, several users

Date: 25 November 2026. The system changes from *one organisation per
account* to **one organisation with several users**, each in one of two
roles. Financial records, calculations and scoring are unchanged.

## 1. Structure

```
One SME organisation (e.g. CrystalCorps Sdn Bhd)
├── CEO / Admin      full authorised access
└── Finance Clerk    restricted accounting access
```

- A user belongs to **one** organisation.
- An organisation can have several CEO / Admins and several Finance Clerks.

## 2. Permissions

Enforced on the **backend** for every request, and mirrored in the
**frontend**. The interface only hides what the API already refuses.

| Feature | CEO / Admin | Finance Clerk | API enforcement |
|---|:-:|:-:|---|
| View financial dashboard and analysis | ✓ | ✗ | `GET /companies/{id}/dashboard/{p}` → 403 |
| View financial health scores and indicators | ✓ | ✗ | `GET /companies/{id}/indicators/{p}` → 403 |
| View the Financial Overview | ✓ | ✗ | `GET /organisation/overview` → 403 |
| View thresholds / scoring methodology | ✓ | ✗ | `GET /thresholds` → 403 |
| Financial simulation (FYP2, not built yet) | ✓ | ✗ | To use `get_admin_company` when built |
| View financial statements (records, calculated statements, trial balance) | ✓ | ✓ | Membership check |
| Import trial balance | ✓ | ✓ | Membership check |
| Create financial records | ✓ | ✓ | Membership check |
| Update financial records (new revision) | ✓ | ✓ | Membership check |
| Delete financial records (by deleting the period) | ✓ | ✗ | `DELETE …/reporting-periods/{id}` → 403 |
| Reporting periods | Full CRUD | Create, read, update | DELETE → 403 |
| Manage users and roles | ✓ | ✗ | `/organisation/members*` → 403 |
| Company settings | ✓ | ✗ | `PUT /companies/{id}` → 403 |

**Status codes:**
- **404:** the company belongs to another organisation. The API does not
  confirm that the identifier exists.
- **403:** the user is a member of the organisation but lacks the role. The
  message explains what Finance Clerks can and cannot do.

The table above is also kept in code: `PERMISSIONS` in
`backend/app/api/dependencies.py`.

## 3. Login flow

```
User logs in → backend returns their organisation and role (GET /organisation)
             ├─ CEO / Admin   → Financial Overview (dashboard, analysis, settings, users)
             └─ Finance Clerk → Financial Data (latest period: trial balance, entries)
```

| | CEO / Admin | Finance Clerk |
|---|---|---|
| Lands on | `/overview` | `/data` (latest period by date) |
| Navigation | Financial Overview · Financial Data · Financial Analysis · Financial History · Company Settings | Financial Data · Financial History |
| Header | Name and "CEO / Admin" | Name and "Finance Clerk" |
| After saving financial data | Goes to the assessment | Returns to Financial History |
| Period cards | Edit period · Delete · Edit data · Dashboard | Edit period · Edit data |

If a Finance Clerk opens an admin address directly (`/overview`,
`/analysis`, `/periods/{id}/dashboard`, `/settings`), they see **"Not
available for your role"** with a link to Financial Data. No confidential
data is fetched, and the API would refuse it anyway.

## 4. Managing users

> **Updated after the code audit (see `AUDIT_FIXES.md`).** People no longer
> join by email alone.

In **Company Settings → Users and roles** (CEO / Admin only):

- **Invite someone:** enter their email and role. The system creates a
  **single-use link that expires in 7 days**.
  - It is shown once, and only a hash of its token is stored.
  - The admin sends the link to the person.
- **Joining:** the person opens the link, signs in (or registers) **with the
  invited email**, and must click **Accept**. Nothing happens automatically,
  including for existing accounts.
- **Refusals:**
  - wrong email address (403);
  - a used, expired or revoked link (410);
  - an account already in an organisation (409).
- **Revoke** a pending invitation at any time. A new invitation for the same
  email replaces the old one.
- **Change a role** from the list; **remove a user** after a confirmation.
  Their account and the data they entered are kept.
- **Activity log:** every change to data and access, with who made it.

Safeguards:
- The founding account cannot be demoted or removed.
- At least one active CEO / Admin always remains.
- A person belongs to one organisation.

## 5. Data model and migration

New table `organisation_members`:

| Column | Notes |
|---|---|
| `company_id` | The organisation |
| `user_id` | Unique: a user is in at most one organisation. Empty while invited. |
| `email` | Lower-case; unique |
| `role` | `admin` or `clerk` |
| `status` | `active` or `invited` |

Migration `c9e5a1b3d742_organisation_members_and_roles`:
- Makes the owner of every existing organisation its **active CEO /
  Admin**, so current accounts keep full access.
- Changes **no** company, period, record or trial balance row.
- Was rehearsed on a copy of the live database (both organisations got
  their owner as admin; all 7 records were kept; downgrade and re-upgrade
  worked), then applied after a backup.
- `companies.owner_id` is kept as "the account that set the organisation
  up".
- The one-primary-company index is unchanged.

## 6. Files

**Backend**
- `app/models/membership.py` (new); `app/models/__init__.py`.
- `alembic/versions/c9e5a1b3d742_…` (new).
- `app/api/dependencies.py`:
  - new: `find_membership` (which also accepts a pending invitation),
    `company_for_member`, `get_admin_company`, `require_admin`,
    `PERMISSIONS`;
  - `get_owned_company` now means "any member".
- `app/api/routes/organisation.py`:
  - status includes `role`;
  - setup and selection create the admin membership;
  - the overview is admin-only;
  - new members endpoints: `GET`, `POST`, `PATCH`, `DELETE
    /organisation/members`.
- `app/schemas/organisation.py`: `role`, member schemas.
- `app/api/routes/dashboard.py`, `indicators.py`, `thresholds.py`: admin
  only.
- `app/api/routes/companies.py`: company settings and period deletion are
  admin only.
- `app/api/routes/financial_records.py`, `trial_balance.py`: record-level
  checks use membership.

**Frontend**
- `context/OrganisationContext.jsx`: `role`, `isAdmin`, each role's home
  and first breadcrumb, `AdminOnly`.
- `App.jsx`: role-based home, admin-only routes, and a "latest period" route
  that does not depend on admin data.
- `layouts/AppLayout.jsx`: navigation per role, role under the user's name.
- `pages/CompanySettingsPage.jsx`: Users and roles section.
- `components/PeriodCard.jsx`, `pages/CompanyDetailPage.jsx`,
  `pages/FinancialDataPage.jsx`: role-aware buttons, breadcrumbs and
  after-save destination.
- Login, registration and setup go to `/`, which routes by role.
- `services/apiClient.js`, `styles.css`.

## 7. Tests

| Suite | Result |
|---|---|
| Backend | **456 passed** (17 new in `tests/integration/test_roles_api.py`) |
| Frontend | **78 passed** (8 new) |

**Backend tests cover:**
- each user sees their role;
- a clerk gets 403 on the overview, dashboard, indicators, thresholds,
  members, company settings and period deletion, and nothing changes;
- a clerk cannot set up a second organisation;
- a clerk can create, read and update periods and records, import a trial
  balance and view the calculated statements;
- an admin has full access;
- promoting a clerk takes effect immediately;
- members are listed with their roles, and an invited person joins on
  registering;
- one organisation per person;
- the owner and last-admin safeguards;
- removing a member ends access but keeps the data;
- isolation between organisations.

**Frontend tests cover:**
- a clerk lands on Financial Data with two navigation items;
- each admin page shows "Not available for your role";
- period cards for a clerk have no Delete or Dashboard;
- an admin's Users and roles section (adding a user, the protected owner,
  the confirmation on removal);
- an admin's full navigation.

**Two existing tests** that called the thresholds endpoint from an account
with no organisation now create one first: thresholds are admin-only.

**Checked in the browser with test accounts:**
1. The admin invited `clerk-check@example.com` as a Finance Clerk.
2. Registering with that email joined the organisation automatically.
3. The clerk landed on Financial Data, with only Financial Data and
   Financial History in the navigation.
4. Opening a dashboard address showed "Not available for your role".
5. Calling `/api/organisation/overview` directly with the clerk's token
   returned 403.

## 8. Limitations

1. **Financial simulation** does not exist yet (FYP2). When it is built,
   its routes should use `get_admin_company` so they are CEO / Admin only.
2. **Invitations are not emailed.** The admin tells the person to register
   with that email.
3. **Changes are not logged.** Each financial record revision is kept, but
   who made each one is not recorded yet. Adding `created_by` to records
   would show which user entered each revision.
4. **No custom roles.** There are two fixed roles.
