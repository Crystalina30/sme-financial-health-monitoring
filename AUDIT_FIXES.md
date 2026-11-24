# Fixes for FYP2_CODEBASE_AUDIT.md

Date: 24 November 2026. Branch: `audit-fixes`, created from `main` with the
uncommitted work carried over; nothing has been committed. The database was
backed up before the migration, and the migration was rehearsed on a copy
first.

| # | Audit finding | Severity | Status |
|---|---|---|---|
| 1 | Invitations could be claimed by email alone | Critical | **Fixed** |
| 2 | Missing inventory inferred as "no stock" | High | **Fixed** |
| 3 | Direct COGS mixed with purchases accepted | High | **Fixed** |
| 4 | Current-asset parts could exceed current assets | High | **Fixed** |
| 5 | Stale revisions editable; races could 500 | High | **Fixed** |
| 6 | Infinity/NaN not rejected uniformly | High | **Fixed** (plus a related 500, found while testing) |
| 7 | No attribution of financial edits | Medium | **Fixed** |
| 8 | Secrets and personal files in the shared ZIP | Medium | **Fixed for future archives**; secret rotation is your decision (§8) |
| 9 | Production hardening | Medium | **Partly**: production guard added; localhost-only DB port not possible on this machine (§9); token storage documented |
| 10 | Methodology and scope | Academic | Unchanged; already described accurately (§10) |

---

## 1. Invitations (critical)

**Before.**
- An admin added an email.
- Whoever registered that email first was given the role, admin included.
- Existing accounts were added without being asked.

**After.**
- **Single-use, random, expiring tokens.**
  - `secrets.token_urlsafe(32)`, valid for 7 days.
  - Only the SHA-256 hash is stored (`organisation_invitations.token_hash`).
  - The admin sees the link once.
- **Explicit acceptance by the intended recipient.**
  `POST /organisation/invitations/accept {token}` needs a signed-in user
  whose email is the invited email. Refusals:

  | Case | Response |
  |---|---|
  | Wrong email | 403 |
  | Used, expired or revoked | 410 |
  | Already in or owns an organisation | 409 |
  | Unknown token | 404 |

- **No automatic joining.** `find_membership` returns only memberships that
  have been accepted. The lazy "claim by email" code is gone, and direct
  `POST /organisation/members` is removed.
- **Revocation and replacement.** An admin can revoke an invitation
  (`DELETE /organisation/invitations/{id}`). A new invitation for the same
  email revokes the pending one. Used and revoked invitations are kept as a
  record.
- **Frontend.**
  - Settings shows the link once (with Copy) and lists invitations with
    their state and a Revoke button.
  - `/join?token=…` previews the invitation and has an **Accept** button. It
    warns when you are signed in with a different email.
  - If you are not signed in, the link is remembered through sign-in or
    registration.
  - The setup page offers "Joining your company? Paste your invitation link".
- **Migration.** Old `invited` member rows are deleted. There were none in
  the live database.

**Remaining.** Email addresses are still **not verified** at registration,
because the project has no mail server. The token is the proof that the
recipient received the link from the admin, and the email must also match.
With a mail service, the next step would be a verification link at
registration.

## 2–3. Stock and cost of sales (high)

`_inventory_treatment` no longer draws a conclusion from an account being
absent.

| Situation | Before | After |
|---|---|---|
| Purchases, no stock accounts (audit's reproduction: sales 200, purchases 100, cash 100) | "purchases_only", no warning | **Material** `stock_not_confirmed`: needs a stock count or an explicit "no stock" confirmation |
| Purchases **and** a cost-of-goods-sold account (audit's reproduction: 200 + 150) | "perpetual", COGS 350, no warning | **Material** `mixed_cost_of_sales`: possible double count; needs recategorising (purchases to inventory in a perpetual system) or an explicit "separate costs" confirmation |
| Perpetual with purchases capitalised to inventory | accepted | accepted (unchanged) |
| Periodic with opening stock and closing count | accepted | accepted (unchanged) |

Resolving these findings:
- Each confirmation is a **visible adjustment row**, added from the
  trial-balance editor's stock panel. It is saved with the trial balance and
  recorded in the audit trail, with the user and date.
- A stock count gives Dr inventory / Cr cost of sales. In the audit's
  purchases-only case, a count of 30 gives COGS 70 and inventory 30.

## 4. Sum of current-asset parts (high)

New blocking check:

    cash + receivables + inventory ≤ current assets

The tolerance is rounding only. Receivables are already net of the
allowance, so every part is non-negative.

The audit's reproduction (cash 80k + receivables 70k against current
assets 100k) is now refused: "Cash, receivables and inventory together
(150,000.00) exceed current assets (100,000.00) by 50,000.00."

## 5. Stale and concurrent revisions (high)

- **Only the current revision can be corrected.** Editing a superseded
  revision returns **409**: "Revision 1 has been superseded by revision 2.
  Reload…".
- **Serialisation.** Writing a revision first takes a row lock on the
  reporting period (`SELECT … FOR UPDATE` on PostgreSQL), then re-reads.
  This applies to statement entry and trial balance submission alike.
- **Database guarantee.** The partial unique index
  `uq_record_one_current_per_period` allows at most one current revision per
  period. A lost race returns **409**, not a 500 (`commit_revision`).

## 6. Non-finite numbers (high)

- `allow_inf_nan=False` on `FinancialInputs` and on every request model that
  carries amounts: records, trial balance lines and suggestions.
- `to_money` refuses non-finite values.
- The importer's `parse_amount` and `parse_balance` treat `inf`, `nan` and
  `1e999` as "not a number" and report the row.
- **Also fixed:** FastAPI echoes invalid input back in its 422 response, and
  `Infinity` cannot be written as JSON. That turned the correct 422 into a
  500. A validation-error handler now reports such inputs as text.

## 7. Audit trail and attribution (medium)

- **`financial_records.created_by_user_id`**: who entered each revision.
  Shown as "Entered by …" on the period card and returned as
  `created_by_email`.
- **`audit_events`**: append-only, written in the same transaction as the
  change it records. Events:
  - organisation created; company settings changed (from and to);
  - period created, updated (from and to) and **deleted**, with a snapshot of
    every revision's key figures;
  - record created; record corrected (from and to revision, and **each
    changed field from and to**);
  - trial balance imported, with the line count, the stock method and
    **every period-end adjustment** (stock counts and confirmations);
  - invitation created, revoked and accepted; role changed; member removed.
- **Reading the log.** `GET /organisation/audit-log` is admin-only, and
  there is no endpoint to change or delete entries. Settings has an
  **Activity log** section.
- **Destructive operations.** Deleting a period now needs
  `confirm_label=<period label>` in the request, so a wrong or replayed id
  cannot delete the wrong period. The interface's confirmation dialog sends
  it.

## 8. Packaging and secrets (medium)

- **`scripts/make_source_zip.py`** builds `release/FYP-source-<date>.zip`.
  `release/` is git-ignored. The archive excludes:
  - `.env` and every `.env.*` except `.env.example`;
  - `.git`, `.claude`, `node_modules`, `dist`, caches;
  - PDF, Word and other documents outside `docs/`, including `Sample/`.

  The current archive has 182 files and only `.env.example`. Run
  `python scripts/make_source_zip.py --list` to check before sharing.
- **Rotate the secrets (your decision).** The ZIP you shared earlier
  contained your real `.env`, with the database password and the JWT
  signing secret. If that ZIP left your own machine, both should be changed:
  1. Set a new `JWT_SECRET_KEY` in `.env`. Everyone must then sign in again.
  2. Change the database password with `ALTER USER` and update
     `POSTGRES_PASSWORD` in `.env`.

  I have not done this, because it changes your credentials.

## 9. Production hardening (medium)

- **Production guard.** With `ENVIRONMENT=production`, the backend **refuses
  to start** when the JWT secret is the default or shorter than 32
  characters, the database password is the default, or CORS uses a
  wildcard. Verified: it fails with a clear message.
- **Database port.** Publishing PostgreSQL on `127.0.0.1:5432` only was
  tried, but it **cannot be used on this machine**: Windows' WSL relay
  (`wslrelay`) already listens on 127.0.0.1:5432. The database container
  then failed to start, and the backend was unavailable for about a minute
  while I restored the original binding. No data was affected (7 records
  before and after). Alternatives if you want it:
  - publish it on another localhost port, such as `"127.0.0.1:5433:5432"`,
    and point local tools there;
  - remove the `ports` entry entirely if no tool on the host needs the
    database.
- **Tokens in `localStorage`** and logout without server-side revocation are
  unchanged. They are documented as a limitation for this local deployment.
  Moving to HttpOnly cookies with server-side session revocation would be the
  production change.

## 10. Methodology and scope (academic)

No code change was needed. The project already describes these points
accurately:
- the health score is an explainable **project index**, not a validated
  default-prediction model;
- "Checks passed" means internal consistency, **not an audit**;
- the input is a **trial balance**, not raw journals;
- **Altman Z″** is a separate benchmark, not a calibrated probability for
  Malaysian SMEs.

These should also be stated in the FYP report.

## Tests

| Suite | Before | After |
|---|---|---|
| Backend (pytest) | 456 | **490 passed** |
| Frontend (Vitest) | 78 | **81 passed** |
| Production build | Passes | Passes |

**New tests:**
- `tests/integration/test_audit_fixes.py`:
  - **invitations:** impostor registration gets no access, hash-only
    storage, explicit acceptance, wrong email, replay, expiry, revocation,
    replacement, unknown token, cross-organisation, clerk cannot invite,
    existing members;
  - **revisions:** stale edits, the one-current index, duplicate first
    records;
  - **non-finite input:** records and trial balance;
  - **audit trail:** attribution and full log order, confirmation required
    to delete, stock confirmations kept as evidence.
- **Unit tests:** the audit's two inventory reproductions, confirmations,
  counting, the mixed-postings review, the sum of current assets, and
  non-finite values in the model, `to_money` and the importer.
- **Frontend:** the invitation link and list, revoke only when pending, the
  activity log, and the join page (accept, wrong email, expired).

**Updated tests, because the behaviour changed deliberately:**
- role tests now join through invitations;
- deleting a period names it;
- one validation fixture had current-asset parts larger than current
  assets.

**Verified on the running system:**
- the migration applied, with records unchanged;
- an invitation was created, shown as a link, revoked, and both events
  appear in the activity log;
- a bug found during this check is fixed: the activity log now refreshes
  after changes.

## Not done here (from the audit's recommended order, step 7)

- A full end-to-end test of both roles against a live PostgreSQL database
  (for example with Playwright).
- A documented accounting validation study using additional reference
  statements, as recommended in `ACCOUNTING_DATASET_VALIDATION.md`.
