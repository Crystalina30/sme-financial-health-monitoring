import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../services/apiClient.js';

export default function CompanyDetailPage() {
  const { companyId } = useParams();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ label: '', period_start: '', period_end: '' });

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

  const createPeriod = useMutation({
    mutationFn: () => api.createPeriod(companyId, form),
    onSuccess: () => {
      setForm({ label: '', period_start: '', period_end: '' });
      queryClient.invalidateQueries({ queryKey: ['periods', companyId] });
    },
  });

  const recordsByPeriod = new Map(
    (records.data || []).map((record) => [record.reporting_period_id, record]),
  );

  return (
    <div className="page">
      <p className="breadcrumb">
        <Link to="/companies">Companies</Link> / {company.data?.name || '…'}
      </p>
      <h1>{company.data?.name || 'Company'}</h1>

      <section className="card">
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
              onChange={(e) => setForm({ ...form, period_start: e.target.value })}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="end">End</label>
            <input
              id="end"
              type="date"
              value={form.period_end}
              onChange={(e) => setForm({ ...form, period_end: e.target.value })}
              required
            />
          </div>
          <button type="submit" className="button" disabled={createPeriod.isPending}>
            Add period
          </button>
        </form>
        {createPeriod.isError && (
          <p className="alert alert-error">{createPeriod.error.message}</p>
        )}
      </section>

      <section className="card">
        <h2>Reporting periods</h2>
        {periods.isLoading && <p className="muted">Loading…</p>}
        {periods.data?.length === 0 && (
          <p className="muted">No reporting periods yet.</p>
        )}

        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Start</th>
                <th>End</th>
                <th>Financial data</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {periods.data?.map((period) => {
                const record = recordsByPeriod.get(period.id);
                return (
                  <tr key={period.id}>
                    <td>{period.label}</td>
                    <td>{period.period_start}</td>
                    <td>{period.period_end}</td>
                    <td>
                      {record ? (
                        <span className="pill pill-sound">
                          Entered (revision {record.revision})
                        </span>
                      ) : (
                        <span className="pill pill-muted">Not entered</span>
                      )}
                    </td>
                    <td className="actions-cell">
                      <Link
                        className="button button-small"
                        to={`/companies/${companyId}/periods/${period.id}/data`}
                      >
                        {record ? 'Edit data' : 'Enter data'}
                      </Link>
                      {record && (
                        <Link
                          className="button button-small button-quiet"
                          to={`/companies/${companyId}/periods/${period.id}/dashboard`}
                        >
                          Dashboard
                        </Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
