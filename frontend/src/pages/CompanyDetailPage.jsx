import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import Icon from '../components/Icon.jsx';
import PeriodCard from '../components/PeriodCard.jsx';
import { useBreadcrumbs } from '../context/BreadcrumbContext.jsx';
import { useOrganisation } from '../context/OrganisationContext.jsx';
import { api } from '../services/apiClient.js';
import { formatPeriodDates, oneYearEnd, periodLengthDays } from '../utils/format.js';

export default function CompanyDetailPage() {
  const { companyId, isAdmin, homeCrumb } = useOrganisation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ label: '', period_start: '', period_end: '' });
  // A reporting period is normally a year: choosing a start fills in the
  // end a year later, until the user sets the end themselves.
  const [endTouched, setEndTouched] = useState(false);

  const company = useQuery({
    queryKey: ['company', companyId],
    queryFn: () => api.getCompany(companyId),
  });
  const periods = useQuery({
    queryKey: ['periods', companyId],
    queryFn: () => api.listPeriods(companyId),
  });
  const records = useQuery({
    queryKey: ['records', companyId],
    queryFn: () => api.listRecords(companyId),
  });

  useBreadcrumbs([
    ...(isAdmin ? [homeCrumb] : []),
    { label: 'Financial History' },
  ]);

  const createPeriod = useMutation({
    mutationFn: () => api.createPeriod(companyId, form),
    onSuccess: () => {
      setForm({ label: '', period_start: '', period_end: '' });
      setEndTouched(false);
      refresh();
    },
  });

  // Anything that shows periods or their figures is refreshed after a change.
  function refresh() {
    ['periods', 'records', 'overview', 'dashboard', 'trial-balance'].forEach((key) =>
      queryClient.invalidateQueries({ queryKey: [key] }),
    );
  }
  const newDays = periodLengthDays(form.period_start, form.period_end);

  const recordsByPeriod = new Map(
    (records.data || []).map((record) => [record.reporting_period_id, record]),
  );

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <h1>{company.data?.name || 'Company'}</h1>
          {company.data && (
            <p className="page-subtitle">
              {company.data.industry || 'Industry not recorded'} · Figures in{' '}
              {company.data.currency_code}
            </p>
          )}
        </div>
      </div>

      <div className="company-layout">
        <section className="card company-layout-aside reveal">
          <h2>Add a reporting period</h2>
          <form
            className="inline-form"
            onSubmit={(event) => {
              event.preventDefault();
              createPeriod.mutate();
            }}
          >
            <div className="field">
              <label htmlFor="label">Label</label>
              <input
                id="label"
                placeholder="FY2025"
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="start">Start</label>
              <input
                id="start"
                type="date"
                value={form.period_start}
                onChange={(e) => {
                  const start = e.target.value;
                  setForm({
                    ...form,
                    period_start: start,
                    period_end: !endTouched && start ? oneYearEnd(start) : form.period_end,
                  });
                }}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="end">End</label>
              <input
                id="end"
                type="date"
                value={form.period_end}
                onChange={(e) => {
                  setEndTouched(true);
                  setForm({ ...form, period_end: e.target.value });
                }}
                required
              />
            </div>
            {newDays > 0 && (
              <p className="note">
                {formatPeriodDates(form.period_start, form.period_end)} · {newDays} days
              </p>
            )}
            <button type="submit" className="button" disabled={createPeriod.isPending}>
              <Icon name="plus" />
              Add period
            </button>
          </form>
          {createPeriod.isError && (
            <p className="alert alert-error" style={{ marginTop: 16, marginBottom: 0 }}>
              {createPeriod.error.message}
            </p>
          )}
        </section>

        <section className="card reveal" style={{ '--i': 1 }}>
          <div className="card-header">
            <h2>Reporting periods</h2>
            {periods.data?.length > 0 && (
              <span className="note">
                {periods.data.length} {periods.data.length === 1 ? 'period' : 'periods'}
              </span>
            )}
          </div>
          {periods.isLoading && <p className="muted">Loading…</p>}
          {periods.data?.length === 0 && (
            <p className="empty-state">
              No reporting periods yet. Add one above, then enter its financial data.
            </p>
          )}

          {periods.data?.length > 0 && (
            <ol className="period-list">
              {periods.data.map((period) => {
                const record = recordsByPeriod.get(period.id);
                return (
                  <li key={period.id} className={`period-item${record ? ' has-data' : ''}`}>
                    <PeriodCard
                      period={period}
                      record={record}
                      companyId={companyId}
                      canDelete={isAdmin}
                      canViewDashboard={isAdmin}
                      onChanged={refresh}
                    />
                  </li>
                );
              })}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
