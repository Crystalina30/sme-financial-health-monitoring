# Income Statement Validation and Assessment Reliability

Date: 24 November 2026. This change separates **financial health** (Sound,
Vulnerable, Distressed) from **assessment reliability** (Validated,
Provisional, Insufficient Data), and adds an exact income-statement
reconciliation.

The scoring methodology is unchanged: normalisation, thresholds, arithmetic
aggregation, the geometric robustness comparison and Altman Z″. Your
CrystalCorps scores are the same as before the change (FY2025 73.02,
FY2024 47.25).

---

## 1. Root cause

1. **The reconciliation was too weak.** Net profit was checked against
   `operating profit − interest − tax`, and a difference only produced a
   warning beyond **5% of revenue**. That tolerance:
   - scales with the size of the business (RM60,000 could go unexplained on
     RM1.2 million of revenue);
   - shrinks to almost nothing when revenue itself is the mistyped figure
     (5% of RM1,200 is RM60).
2. **No reliability judgement existed.** The warning was stored as text and
   shown beside the score, but the score and its classification were still
   presented as a normal assessment. Nothing in the API or the interface
   said the assessment could not be relied on.
3. **The input model had no legitimate lines between operating profit and
   net profit** (non-operating income or expenses, other operating income).
   A correct statement with such items could not reconcile, which blurred
   genuine errors with missing fields.
4. **A loss was flagged as a problem.** Cost of goods sold above revenue was
   a warning, although a loss is a financial result, not a data error.

Where validation reached the assessment before:
- `validation_service.validate_financial_inputs` was called when a record
  was saved (`financial_records.py`, `trial_balance.py`).
- Its text went into `FinancialRecord.validation_notes` and
  `accounting_identity_ok`.
- `presenters.build_assessment_response` copied both into the dashboard
  response.
- `DashboardPage` showed them as loose alerts.
- The score trend and the overview ignored them entirely.

## 2. Reconciliation formulas

All amounts are exact decimals to the cent (`to_money`, from the earlier
balance-sheet fix).

```
gross profit        = revenue − cost of goods sold
operating profit    = gross profit + other operating income − operating expenses
profit before tax   = operating profit + other (non-operating) income
                      − other (non-operating) expenses − interest expense
calculated net      = profit before tax − tax expense        (a tax credit is a negative tax expense)
difference          = reported net profit − calculated net profit
reconciled          ⇔ |difference| ≤ RM0.01
```

**Materiality policy.** Net profit is the last line of the same statement as
its components, so a correctly prepared statement reconciles exactly. Any
difference above one presentation unit (RM0.01, the same rule as the
balance-sheet identity) is a **material, unresolved discrepancy**, whatever
its size. The system cannot tell whether a line is missing or a figure is
wrong, so it never guesses. The old 5%-of-revenue rule was evaluated and
rejected for the reasons in §1.

Users fix a discrepancy by correcting the figures or entering the missing
lines. Each correction is saved as a new revision, so it is auditable.
There is deliberately no "dismiss" button.

## 3. New and modified fields

| Field | Meaning | Where it counts |
|---|---|---|
| `other_operating_income` | Operating income that is not revenue: wage subsidies, grants, rental of spare premises | Operating profit (so also interest cover and Z″ X3, through EBIT) |
| `other_income` | Non-operating income: interest and dividends received, gains on disposal | Profit before tax |
| `other_expenses` | Non-operating expenses and losses: losses on disposal, impairment, exchange losses | Profit before tax |

Rules for these fields:
- Each is entered as a positive amount (0 when absent).
- Finance costs stay in `interest_expense`; a tax credit is a negative
  `tax_expense`.
- The definitions do not overlap, so nothing can be counted twice.
- **Effect on scores:** for every existing record these fields are 0. With
  them at 0, `operating_profit` (and therefore interest cover and Z″) is
  exactly what it was before, so existing scores do not change.

Other changes:
- **Trial balance:** two new account categories, *Other operating income*
  and *Other expense (non-operating)*. The existing *Other income* category
  now flows into `other_income` instead of only into net profit. The sample
  trial balance's RM2,000 of interest received now reconciles.
- **Category suggestions:** "Loss on disposal", "exchange loss" and
  "donation" are suggested as *Other expense*; "wage subsidy" and "grant
  income" as *Other operating income*.

## 4. Database migration

`a7c3e91f5b20_income_statement_reconciliation`:
- Adds the three columns to `financial_records` as `NUMERIC(18,2) NOT NULL
  DEFAULT 0`.
- Existing records get 0, which is what they implicitly assumed. No
  existing value is changed.
- Has a downgrade.

Applied to the live database after a backup (5 records; the sum of the new
fields is 0).

## 5. Validation severity

| Severity | Effect | Findings |
|---|---|---|
| **Blocking** | Not saved (422) | Balance-sheet identity beyond RM0.01 (unchanged strict rule); current assets > total assets; current liabilities > total liabilities; inventory or receivables > current assets; trial balance not balanced, uncategorised or with a negative total |
| **Material** | Saved for correction; assessment is **Provisional** | Net profit does not reconcile; trial balance with no closing stock although opening stock is charged; trial balance taken after closing entries; account codes repeated; accounts on the wrong side of their category; an older record stored as failing the identity |
| **Informational** | No effect on reliability | Negative gross profit (a loss); a period that is not a year (scaled correctly); indicators or categories that cannot be calculated; no revenue account |

`ValidationResult` keeps `errors`, `warnings` (material), `is_valid`,
`accounting_identity_ok` and `notes`. It adds `info`, `issues` (each with a
severity and a code) and `reconciliation`.

## 6. Assessment status rules

Worked out by `reliability_service.evaluate_reliability` **from the current
record every time** an assessment is shown: dashboard, score trend and
overview. It is never read from a stored flag, and never inferred from
whether a score exists.

1. **Insufficient data**: there are no total assets, or no category can be
   scored. No score is shown, and the classification is "Insufficient data".
2. **Provisional**: any material finding (§5). The score is calculated and
   shown, but marked as indicative.
3. **Validated**: otherwise.

Correcting a record (a new revision) changes the status of that period
immediately. Earlier revisions are kept unchanged.

## 7. Backend and frontend changes

**Backend**
- `schemas/financial_inputs.py`: the three fields; `operating_profit`
  includes other operating income; new `profit_before_tax`.
- `models/financial_record.py`, `schemas/financial_record.py`,
  `routes/financial_records.py`, `utils/presenters.py`: the fields are
  stored, accepted and returned.
- `services/validation_service.py`: severity model (`Issue`,
  `BLOCKING`/`MATERIAL`/`INFO`), `reconcile_income_statement`, and the
  rewritten net-profit and loss findings.
- `services/reliability_service.py` (new): the status rules.
- `models/enums.py`: `AssessmentStatus`.
- `services/trial_balance_service.py`: new categories and figures, and
  findings with severity (`Derivation.findings`).
- `schemas/assessment.py`: the dashboard response gains `assessment_status`,
  `is_provisional`, `data_quality_issues`,
  `income_statement_reconciliation`, `reported_net_profit`,
  `calculated_net_profit` and `reconciliation_difference`. Each trend point
  gains `assessment_status`.
- `routes/dashboard.py`: the trend carries each period's own status.
- `routes/organisation.py`, `schemas/organisation.py`: the overview gains
  `assessment_status`, `is_provisional` and `reconciliation_difference` per
  period, with the same findings as the dashboard.

Existing fields are kept, so existing consumers keep working.

**Frontend**
- `components/AssessmentStatus.jsx` (new):
  - a **"Data: Validated / Provisional / Insufficient data"** badge, dashed
    and labelled "Data:", so it cannot be mistaken for the Sound /
    Vulnerable / Distressed pill;
  - the banner **"Provisional Assessment — Financial data requires
    review"**, which explains why, shows reported against calculated net
    profit and the difference, and links to "Review financial data";
  - the banner **"Insufficient Data — Financial health cannot be
    assessed"**.
- `ScoreSummary.jsx` and `ScoreCards.jsx`: the badge sits under the score,
  apart from the classification.
- `DashboardPage.jsx`: the banner replaces the old loose identity and
  validation alerts.
- `HealthScoreTrendChart.jsx`: provisional scores are drawn as **hollow
  points** in the warning colour, and the tooltip names the status. The
  card notes "Hollow points are provisional".
- `OverviewPage.jsx`: the badge by the score, a provisional heading on the
  notes box, and a reliability badge for each period in the history table.
- `FinancialDataPage.jsx`: the three optional lines, clearer labels
  ("Interest expense (finance costs)", "Tax expense (negative for a tax
  credit)", "Net profit (as reported)"), and a live **Net profit
  reconciliation** panel. The panel shows gross profit, operating profit,
  profit before tax, calculated and reported net profit, and the exact
  difference, and warns that saving as it is gives a Provisional
  assessment.
- `TrialBalanceEditor.jsx`: the three figures in the calculated statements.

Layout and design are otherwise unchanged.

## 8. Automated test results

| Suite | Before | After |
|---|---|---|
| Backend (pytest) | 404 passed | **425 passed** |
| Frontend (Vitest) | 62 passed | **67 passed** |
| Production build | Passes | Passes |

Two existing tests were updated because they encoded the old behaviour:
- **Backend:** a loss was a warning; it is now informational.
- **Frontend:** the overview's old "Check the data…" wording and its
  "1 warning" column.

New backend tests (`tests/integration/test_assessment_reliability.py` plus
unit tests):
1. A consistent statement is Validated.
2. A loss-making but consistent statement is Validated, and the loss is
   informational.
3. The RM1,198,800 inconsistency is Provisional, with exact gross profit,
   operating profit, calculated net profit and difference. The submitted
   figures are stored unchanged.
4. Legitimate other income and expenses reconcile and give Validated; other
   operating income counts in operating profit.
5. RM0.01 is tolerated and RM0.02 is not.
6. Missing essential figures give Insufficient Data, with no score.
7. A correctly mapped sample trial balance is Validated, with its interest
   received carried as other income.
8. The Tally reference trial balance (no closing stock) is Provisional. Its
   score is still 78.45, so scoring is unchanged.
9. A post-closing trial balance is not Validated.
10. A balance-sheet failure is still rejected (strict RM0.01 rule kept).
11. Correcting a record moves Provisional to Validated on the dashboard and
    the trend, and the earlier revision is kept exactly as entered.
12. The overview reports each period's status and difference.
13. Exact decimal arithmetic, every reconciliation line (including a tax
    credit), the new trial balance categories, severities and suggestions.

New frontend tests: the provisional banner with reconciliation figures and
the review link; health and reliability shown as separate badges; a
validated assessment has no banner; the insufficient-data banner and "N/A"
score; reliability badges in the overview history; the live reconciliation
panel, including a legitimate line that makes the statement reconcile.

Also checked in the browser with the test account:
- saving an inconsistent revision showed the provisional banner (reported
  300,000, calculated 100,000, difference 200,000) and the "Data:
  Provisional" badge beside "Sound";
- correcting it gave "Data: Validated" and no banner;
- all three revisions remain stored.

## 9. Before and after (your real data)

| Period | Before | After |
|---|---|---|
| FY2024 (revenue typed as 1,200) | Score 47.25 Vulnerable, shown normally, plus a vague text warning | Score 47.25 Vulnerable, **Data: Provisional**, banner: "Reported net profit (100,000.00) differs from the calculated net profit (-1,098,800.00) by 1,198,800.00", with a link to review the data. The trend point is hollow. The negative gross profit is a separate informational note. |
| FY2025 | 73.02 Sound | 73.02 Sound, **Data: Validated** (net profit reconciles exactly). The 31-day period remains an informational note. |

## 10. Remaining limitations

1. **The materiality policy is strict by design.** A statement typed from a
   publication rounded to whole ringgit or thousands may be off by a few
   units and show as Provisional. The documented fix is to enter exact
   figures. A selectable presentation unit exists in the validation service
   but is not offered in the interface.
2. **Missing data versus a mistyped figure.** The reconciliation shows that
   the figures do not add up, not which one is wrong.
3. **Trial balance closing information.** Missing closing stock and
   post-closing balances are detected by pattern and balance. A trial
   balance that hides such problems in unusual account names can still pass.
4. **Historical notes.** The `validation_notes` stored with older records
   keep their original wording. The status shown is always recalculated
   from the figures, so it is consistent, but the stored text may describe
   the old rules.
5. **Retained earnings are not reconciled** against the movement in equity.
   Only the balance-sheet identity and the income statement are reconciled.

---

## 11. Follow-up: what "Validated" means, rounded statements, and inventory

### 11.1 "Validated" is shown as "Checks passed"

A statement can reconcile perfectly and still be incomplete: for example, an
expense account left out of a balanced trial balance. The status therefore
means that **the implemented consistency and completeness checks passed**,
not that the figures were audited or proven correct.

* The interface label is now **"Data: Checks passed"**. The API value stays
  `validated`, so existing consumers are unaffected.
* Every assessment returns **`checks_performed`**: each check's name, its
  result (passed, failed, or not applicable) and what it compared. The
  checks are:
  - the balance sheet balances;
  - net profit reconciles with its lines;
  - for trial balances only: debits equal credits and every account is
    categorised; period-end stock is accounted for; there are no
    duplicated, reversed or post-closing balances;
  - there are enough figures to assess.
* The dashboard shows them under **"What was checked"**. It ends with the
  statement that the checks cannot detect an omitted account, or figures
  that are consistent but wrong, and are not an audit.
* For statement totals, the trial balance checks show as **not applicable**:
  completeness cannot be checked account by account.

### 11.2 Rounded published statements

Published reports (for example Maybank's or AirAsia's) present figures in
RM'000 or RM million. Each record now states the precision of its source
figures in `presentation_unit`, which takes one of four values:

| Value | Meaning |
|---|---|
| 0.01 | Exact figures, to the sen (the default) |
| 1 | Rounded to RM1 |
| 1000 | RM'000 |
| 1000000 | RM million |

The migration is `b8d4f0a2c631`; existing records are set to 0.01, so their
checks are unchanged.

**Rounding policy.**
- Exact figures keep the RM0.01 tolerance.
- For rounded figures, each published figure carries up to half a unit of
  rounding, so an equation combining *n* rounded figures can be out by up to
  **n × ½ unit** with nothing wrong:
  - the balance sheet combines 3 figures (1,500 for RM'000);
  - net profit combines the reported figure plus each non-zero line (for
    example 7 × 500 = 3,500 for RM'000).
- Anything larger cannot be rounding.
- It is never a percentage, and it never depends on the size of the company.

Figures are still entered as full amounts (RM'000 × 1,000), so the
amounts and ratios stay in ringgit.

Where the precision is used:
- **Data-entry page:** a "Source of the figures" selector. The live balance
  sheet and net profit panels use the same tolerance and state it.
- **Records from a rounded source:** they carry an informational note saying
  so.
- **Trial balances:** always exact.
- **Unsupported precisions** (for example 500) are refused.

### 11.3 Inventory: closing stock is never assumed to be zero

The trial balance derivation now identifies how stock is accounted for
(`Derivation.inventory`, also returned by the preview):

| Method | How it is recognised | Result |
|---|---|---|
| Periodic, adjusted | Opening stock charged to cost of sales and closing stock credited | Accepted. The closing stock credit must equal the inventory balance, otherwise a material finding. |
| Periodic, not adjusted | Opening stock charged, no closing stock entry, or closing stock shown as nil without crediting cost of sales (the Tally dataset) | **Material**: the stock count is needed |
| Periodic with opening stock still in the inventory account | Purchases charged, no opening or closing entries, and an inventory balance (which is then the opening stock) | **Material**: cost of goods sold and inventory would both be wrong |
| Perpetual / cost of sales recognised | Cost of sales account posted directly and no purchases | Accepted (informational note) |
| Purchases only, or no stock accounts | No stock is carried | Accepted (informational note) |

When the count is needed, the trial balance editor shows a **Period-end stock**
panel. The user either enters the closing stock count or confirms there was
none. Either is added as **visible, removable adjustment rows**, saved with
the trial balance and marked as entered by the user, with the date:

- **Count entered:** Dr inventory / Cr cost of sales.
- **Opening stock still in the inventory account:** the opening stock is
  first moved to cost of sales.
- **No stock confirmed:** a single row, which gives an informational note.

Cost of goods sold is then right, and the adjustment is traceable. With the
Tally reference trial balance:
- with no count, it stays Provisional;
- with a count, cost of goods sold and inventory are adjusted, and the
  checks pass;
- with an explicit nil confirmation, the checks pass with a note, and the
  score is unchanged at 78.45.

### 11.4 Test results after the follow-up

| Suite | Result |
|---|---|
| Backend | **439 passed** (14 new: rounding policy and tolerance, API precision, refused precision, the checks list, and each inventory method, adjustment and confirmation) |
| Frontend | **70 passed** (3 new: what was checked, rounding on the statement form, the closing-stock panel. 3 updated for the "Checks passed" label) |

One existing backend test was updated for the new rounding policy: an
RM'000 statement out by 1,001 now passes (the allowance is 1,500); out by
1,501 fails.

