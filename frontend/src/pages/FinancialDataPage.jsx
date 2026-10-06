import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../services/apiClient.js';

/** Field groups, so the form mirrors the statements it is transcribed from. */
const FIELD_GROUPS = [
  {
    title: 'Income statement',
    fields: [
      ['revenue', 'Revenue'],
      ['cost_of_goods_sold', 'Cost of goods sold'],
      ['operating_expenses', 'Operating expenses'],
      ['interest_expense', 'Interest expense'],
      ['tax_expense', 'Tax expense'],
      ['net_profit', 'Net profit'],
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
    ],
  },
];

const EMPTY_FORM = Object.fromEntries(
  FIELD_GROUPS.flatMap((group) => group.fields).map(([key]) => [key, '']),
);

function toNumber(value) {
  return value === '' ? null : Number(value);
}

export default function FinancialDataPage() {
  const { companyId, periodId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY_FORM);

  const records = useQuery({
    queryKey: ['records', companyId],
    queryFn: () => api.listRecords(companyId),
  });

  const existing = records.data?.find(
    (record) => record.reporting_period_id === Number(periodId),
  );

  // Populate the form from the stored record, so a correction starts from the
  // figures already entered rather than from an empty form.
  useEffect(() => {
    if (!existing) return;
    const populated = { ...EMPTY_FORM };
    Object.keys(EMPTY_FORM).forEach((key) => {
      populated[key] = existing[key] === null ? '' : String(existing[key]);
    });
    setForm(populated);
  }, [existing]);

  const save = useMutation({
    mutationFn: () => {
      const payload = Object.fromEntries(
        Object.entries(form).map(([key, value]) => [
          key,
          key === 'inventory' ? toNumber(value) : Number(value || 0),
        ]),
      );
      if (existing) return api.updateRecord(existing.id, payload);
      return api.createRecord(companyId, {
        ...payload,
        reporting_period_id: Number(periodId),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['records', companyId] });
      navigate(`/companies/${companyId}/periods/${periodId}/dashboard`);
    },
  });

  // The identity is shown live, so a transcription error is visible before
  // the form is submitted rather than only in the server's response.
  const assets = Number(form.total_assets || 0);
  const liabilitiesPlusEquity =
    Number(form.total_liabilities || 0) + Number(form.total_equity || 0);
  const identityDifference = assets - liabilitiesPlusEquity;
  const identityHolds = Math.abs(identityDifference) <= Math.max(1, assets * 0.01);

  return (
    <div className="page">
      <p className="breadcrumb">
        <Link to="/companies">Companies</Link> /{' '}
        <Link to={`/companies/${companyId}`}>Company</Link> / Financial data
      </p>
      <h1>{existing ? 'Correct financial data' : 'Enter financial data'}</h1>
      {existing && (
        <p className="muted">
          Saving stores revision {existing.revision + 1}. The current revision is kept.
        </p>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {FIELD_GROUPS.map((group) => (
          <section className="card" key={group.title}>
            <h2>{group.title}</h2>
            <div className="field-grid">
              {group.fields.map(([key, label]) => (
                <div className="field" key={key}>
                  <label htmlFor={key}>{label}</label>
                  <input
                    id={key}
                    type="number"
                    step="0.01"
                    value={form[key]}
                    onChange={(event) => setForm({ ...form, [key]: event.target.value })}
                    required={key !== 'inventory'}
                  />
                </div>
              ))}
            </div>
          </section>
        ))}

        <section className={`card ${identityHolds ? '' : 'card-warning'}`}>
          <h2>Accounting identity</h2>
          <p className="muted">Total assets must equal total liabilities plus equity.</p>
          <p className={identityHolds ? 'identity-ok' : 'identity-bad'}>
            {identityHolds
              ? 'The identity holds.'
              : `Out by ${identityDifference.toLocaleString()}. The record will be rejected until this is corrected.`}
          </p>
        </section>

        {save.isError && <p className="alert alert-error">{save.error.message}</p>}

        <button type="submit" className="button" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save and assess'}
        </button>
      </form>
    </div>
  );
}
