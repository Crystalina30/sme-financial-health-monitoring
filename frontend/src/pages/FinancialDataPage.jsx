import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import Icon from '../components/Icon.jsx';
import TrialBalanceEditor from '../components/TrialBalanceEditor.jsx';
import { useBreadcrumbs } from '../context/BreadcrumbContext.jsx';
import { useOrganisation } from '../context/OrganisationContext.jsx';
import { api } from '../services/apiClient.js';
import { formatAmount, toCents } from '../utils/format.js';

/** Field groups, so the form mirrors the statements it is transcribed from. */
const FIELD_GROUPS = [
  {
    title: 'Income statement',
    fields: [
      ['revenue', 'Revenue'],
      ['cost_of_goods_sold', 'Cost of goods sold'],
      ['other_operating_income', 'Other operating income (optional, e.g. subsidies, grants)'],
      ['operating_expenses', 'Operating expenses'],
      ['other_income', 'Other non-operating income (optional, e.g. interest received, gains)'],
      ['other_expenses', 'Other non-operating expenses (optional, e.g. losses on disposal)'],
      ['interest_expense', 'Interest expense (finance costs)'],
      ['tax_expense', 'Tax expense (negative for a tax credit)'],
      ['net_profit', 'Net profit (as reported)'],
    ],
  },
  {
    title: 'Balance sheet',
    fields: [
      ['cash_and_equivalents', 'Cash and equivalents'],
      ['accounts_receivable', 'Accounts receivable'],
      ['inventory', 'Inventory (leave blank if not reported)'],
      ['current_assets', 'Current assets'],
      ['total_assets', 'Total assets'],
      ['current_liabilities', 'Current liabilities'],
      ['total_liabilities', 'Total liabilities'],
      ['total_equity', 'Total equity'],
      [
        'retained_earnings',
        'Retained earnings (optional, negative after accumulated losses; used only for the Altman Z″ benchmark)',
      ],
    ],
  },
];

const EMPTY_FORM = Object.fromEntries(
  FIELD_GROUPS.flatMap((group) => group.fields).map(([key]) => [key, '']),
);

// Fields that may be left blank. Blank is sent as null ("not reported"), never
// as zero, because zero is a real value with a different meaning.
const OPTIONAL_FIELDS = new Set(['inventory', 'retained_earnings']);

// The precision the source figures were rounded to. Exact figures are
// checked to RM0.01; a rounded published statement may be out by half a unit
// for each rounded figure in an equation (the documented rounding policy).
const PRECISIONS = [
  ['0.01', 'Exact figures (to the sen), e.g. from the accounting records'],
  ['1', 'Rounded to RM1'],
  ["1000", "Rounded to RM'000 (thousands), as in published annual reports"],
  ['1000000', 'Rounded to RM million'],
];

function toleranceCents(precision, roundedFigures) {
  const unitCents = Math.round(Number(precision) * 100);
  return unitCents === 1 ? 1 : (unitCents / 2) * Math.max(roundedFigures, 1);
}
// Lines that are zero when the statement has none: blank is sent as 0.
const ZERO_IF_BLANK = new Set(['other_operating_income', 'other_income', 'other_expenses']);

function toNumber(value) {
  return value === '' ? null : Number(value);
}

export default function FinancialDataPage() {
  const { periodId } = useParams();
  const { companyId, isAdmin, homeCrumb } = useOrganisation();
  // The overview's quick actions open the page in a chosen mode.
  const [searchParams] = useSearchParams();
  const requestedMode = searchParams.get('mode');
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY_FORM);
  const [precision, setPrecision] = useState('0.01');
  // How the data is entered. A trial balance is the raw form an accountant
  // exports; statement totals are for when only finished statements exist.
  const [mode, setMode] = useState(null);

  const records = useQuery({
    queryKey: ['records', companyId],
    queryFn: () => api.listRecords(companyId),
  });
  const company = useQuery({
    queryKey: ['company', companyId],
    queryFn: () => api.getCompany(companyId),
  });
  const periods = useQuery({
    queryKey: ['periods', companyId],
    queryFn: () => api.listPeriods(companyId),
  });
  const period = periods.data?.find((item) => item.id === Number(periodId));
  const currency = company.data?.currency_code;

  useBreadcrumbs([
    homeCrumb,
    ...(isAdmin ? [{ label: period ? period.label : 'Period', to: '/history' }] : []),
    { label: 'Financial Data' },
  ]);

  const existing = records.data?.find(
    (record) => record.reporting_period_id === Number(periodId),
  );

  // Open in the mode the stored record was entered in; a new period starts
  // with the trial balance.
  useEffect(() => {
    if (mode !== null || !records.data) return;
    if (requestedMode === 'statement' || requestedMode === 'trial_balance') {
      setMode(requestedMode);
      return;
    }
    setMode(existing?.source === 'statement' ? 'statement' : 'trial_balance');
  }, [mode, records.data, existing, requestedMode]);

  // Populate the form from the stored record, so a correction starts from the
  // figures already entered rather than from an empty form.
  useEffect(() => {
    if (!existing) return;
    const populated = { ...EMPTY_FORM };
    Object.keys(EMPTY_FORM).forEach((key) => {
      populated[key] = existing[key] === null ? '' : String(existing[key]);
    });
    setForm(populated);
    if (existing.presentation_unit) setPrecision(String(Number(existing.presentation_unit)));
  }, [existing]);

  const save = useMutation({
    mutationFn: () => {
      const payload = Object.fromEntries(
        Object.entries(form).map(([key, value]) => [
          key,
          OPTIONAL_FIELDS.has(key) ? toNumber(value) : Number(value || 0), // blank lines are 0
        ]),
      );
      payload.presentation_unit = Number(precision);
      if (existing) return api.updateRecord(existing.id, payload);
      return api.createRecord(companyId, {
        ...payload,
        reporting_period_id: Number(periodId),
      });
    },
    onSuccess: () => afterSave(),
  });

  function afterSave() {
    queryClient.invalidateQueries({ queryKey: ['records', companyId] });
    queryClient.invalidateQueries({ queryKey: ['trial-balance'] });
    queryClient.invalidateQueries({ queryKey: ['overview'] });
    // The CEO / Admin goes on to the assessment; a Finance Clerk, who may
    // not see it, returns to the reporting periods.
    navigate(isAdmin ? `/periods/${periodId}/dashboard` : '/history', {
      state: isAdmin ? undefined : { saved: period?.label },
    });
  }

  // The identity is shown live, so a transcription error is visible before
  // the form is submitted rather than only in the server's response.
  // The income statement rebuilt from its lines, in whole cents, exactly as
  // the server reconciles it. Net profit as reported must equal it to RM0.01.
  const cents = (key) => toCents(form[key]);
  const grossProfit = cents('revenue') - cents('cost_of_goods_sold');
  const operatingProfit = grossProfit + cents('other_operating_income') - cents('operating_expenses');
  const profitBeforeTax =
    operatingProfit + cents('other_income') - cents('other_expenses') - cents('interest_expense');
  const calculatedNetProfit = profitBeforeTax - cents('tax_expense');
  const netProfitDifference = cents('net_profit') - calculatedNetProfit;
  const roundedLines = ['revenue', 'cost_of_goods_sold', 'other_operating_income',
    'operating_expenses', 'other_income', 'other_expenses', 'interest_expense', 'tax_expense']
    .filter((key) => cents(key) !== 0).length;
  const netProfitTolerance = toleranceCents(precision, roundedLines + 1);
  const netProfitReconciles = Math.abs(netProfitDifference) <= netProfitTolerance;
  const incomeStatementEntered = form.revenue !== '' || form.net_profit !== '';

  // Worked in whole cents and held to RM0.01, exactly as the server checks it.
  const assetsCents = toCents(form.total_assets);
  const liabilitiesPlusEquityCents = toCents(form.total_liabilities) + toCents(form.total_equity);
  const differenceCents = assetsCents - liabilitiesPlusEquityCents;
  const identityTolerance = toleranceCents(precision, 3);
  const identityHolds = Math.abs(differenceCents) <= identityTolerance;
  const money = (cents) => `${currency ? `${currency} ` : ''}${formatAmount(cents / 100)}`;

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <h1>{existing ? 'Correct financial data' : 'Enter financial data'}</h1>
          <p className="page-subtitle">
            {existing
              ? `Saving stores revision ${existing.revision + 1}. The current revision is kept.`
              : 'Enter the trial balance for this period, or the totals from finished statements.'}
          </p>
        </div>
      </div>

      <div className="mode-switch" role="group" aria-label="How to enter the data">
        {[
          ['trial_balance', 'Trial balance'],
          ['statement', 'Statement totals'],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={mode === value}
            onClick={() => setMode(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === 'trial_balance' && (
        <TrialBalanceEditor
          companyId={companyId}
          periodId={periodId}
          existing={existing}
          currency={currency}
          onSaved={afterSave}
        />
      )}

      {mode === 'statement' && (
        <form
          className="data-entry"
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          <div>
            <section className="card reveal">
              <h2>Source of the figures</h2>
              <div className="field">
                <label htmlFor="presentation_unit">The figures are</label>
                <select
                  id="presentation_unit"
                  value={precision}
                  onChange={(event) => setPrecision(event.target.value)}
                >
                  {PRECISIONS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <p className="field-hint">
                Always enter full amounts in ringgit: a figure of 1,234 in RM'000 is entered as
                1234000. For rounded statements the checks allow only the difference rounding can
                cause (half a unit for each rounded figure), never a percentage.
              </p>
            </section>
            {FIELD_GROUPS.map((group, index) => (
              <section className="card reveal" key={group.title} style={{ '--i': index }}>
                <h2>{group.title}</h2>
                <div className="field-grid">
                  {group.fields.map(([key, label]) => (
                    <div className="field" key={key}>
                      <label htmlFor={key}>{label}</label>
                      <div className="money-input">
                        {currency && <span aria-hidden="true">{currency}</span>}
                        <input
                          id={key}
                          type="number"
                          step="0.01"
                          inputMode="decimal"
                          value={form[key]}
                          onChange={(event) => setForm({ ...form, [key]: event.target.value })}
                          required={!OPTIONAL_FIELDS.has(key) && !ZERO_IF_BLANK.has(key)}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>

          <aside className="data-entry-aside">
            <section
              className={`card reveal ${identityHolds ? '' : 'card-warning'}`}
              style={{ '--i': 2 }}
              aria-live="polite"
            >
              <h2>Accounting identity</h2>
              <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                Total assets must equal total liabilities plus equity.
              </p>
              <dl className="identity-figures">
                <div>
                  <dt>Total assets</dt>
                  <dd>{money(assetsCents)}</dd>
                </div>
                <div>
                  <dt>Liabilities + equity</dt>
                  <dd>{money(liabilitiesPlusEquityCents)}</dd>
                </div>
              </dl>
              <p className={identityHolds ? 'identity-ok' : 'identity-bad'}>
                <Icon name={identityHolds ? 'check' : 'alert'} />
                {identityHolds
                  ? 'The identity holds.'
                  : `Out by ${money(Math.abs(differenceCents))}: total assets are ${
                      differenceCents > 0 ? 'higher' : 'lower'
                    } than liabilities plus equity. They must agree to within ${formatAmount(identityTolerance / 100)}; the record will be rejected until this is corrected.`}
              </p>
            </section>

            {incomeStatementEntered && (
              <section
                className={`card reveal ${netProfitReconciles ? '' : 'card-warning'}`}
                style={{ '--i': 3 }}
                aria-live="polite"
              >
                <h2>Net profit reconciliation</h2>
                <dl className="identity-figures">
                  {[
                    ['Gross profit', grossProfit],
                    ['Operating profit', operatingProfit],
                    ['Profit before tax', profitBeforeTax],
                    ['Calculated net profit', calculatedNetProfit],
                    ['Reported net profit', cents('net_profit')],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{money(value)}</dd>
                    </div>
                  ))}
                </dl>
                <p className={netProfitReconciles ? 'identity-ok' : 'identity-bad'}>
                  <Icon name={netProfitReconciles ? 'check' : 'alert'} />
                  {netProfitReconciles
                    ? 'Net profit reconciles with its lines.'
                    : `Reported net profit differs from the calculated figure by ${money(
                        Math.abs(netProfitDifference),
                      )} (rounding allowed: ${formatAmount(netProfitTolerance / 100)}). Correct the figures or enter the missing income or expense lines. If you save as it is, the assessment will be Provisional until it is corrected.`}
                </p>
              </section>
            )}

            {save.isError && <p className="alert alert-error">{save.error.message}</p>}

            <button type="submit" className="button" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save and assess'}
            </button>
          </aside>
        </form>
      )}
    </div>
  );
}
