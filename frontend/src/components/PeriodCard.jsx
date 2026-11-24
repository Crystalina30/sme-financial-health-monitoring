import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';

import ConfirmDialog from './ConfirmDialog.jsx';
import Icon from './Icon.jsx';
import { api } from '../services/apiClient.js';
import { formatPeriodDates, periodLengthDays } from '../utils/format.js';

/** Inline form to correct a period's label and dates. */
function PeriodEditForm({ period, companyId, hasData, onDone, onCancel }) {
  const [form, setForm] = useState({
    label: period.label,
    period_start: period.period_start,
    period_end: period.period_end,
  });
  const save = useMutation({
    mutationFn: () => api.updatePeriod(companyId, period.id, form),
    onSuccess: onDone,
  });
  const days = periodLengthDays(form.period_start, form.period_end);

  return (
    <form
      className="period-edit"
      aria-label={`Edit ${period.label}`}
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <div className="period-edit-fields">
        <div className="field">
          <label htmlFor={`label-${period.id}`}>Label</label>
          <input
            id={`label-${period.id}`}
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
            required
            maxLength={50}
          />
        </div>
        <div className="field">
          <label htmlFor={`start-${period.id}`}>Start</label>
          <input
            id={`start-${period.id}`}
            type="date"
            value={form.period_start}
            onChange={(e) => setForm({ ...form, period_start: e.target.value })}
            required
          />
        </div>
        <div className="field">
          <label htmlFor={`end-${period.id}`}>End</label>
          <input
            id={`end-${period.id}`}
            type="date"
            value={form.period_end}
            onChange={(e) => setForm({ ...form, period_end: e.target.value })}
            required
          />
        </div>
      </div>
      <p className="note">
        {days > 0 ? `${days} days. ` : ''}
        {hasData &&
          'The financial data entered for this period is kept; ratios that depend on the ' +
            'period length are recalculated with the new dates.'}
      </p>
      {save.isError && <p className="alert alert-error">{save.error.message}</p>}
      <div className="actions-cell">
        <button type="button" className="button button-small button-quiet" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="button button-small" disabled={save.isPending}>
          <Icon name="check" />
          {save.isPending ? 'Saving…' : 'Save period'}
        </button>
      </div>
    </form>
  );
}

/** One reporting period in the history list, with its actions. */
export default function PeriodCard({
  period,
  record,
  companyId,
  onChanged,
  canDelete = true,
  canViewDashboard = true,
}) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const remove = useMutation({
    mutationFn: () => api.deletePeriod(companyId, period.id, period.label),
    onSuccess: () => {
      setConfirming(false);
      onChanged();
    },
  });

  const days = periodLengthDays(period.period_start, period.period_end);

  return (
    <div className={`period-card${editing ? ' is-editing' : ''}`}>
      {editing ? (
        <PeriodEditForm
          period={period}
          companyId={companyId}
          hasData={Boolean(record)}
          onCancel={() => setEditing(false)}
          onDone={() => {
            setEditing(false);
            onChanged();
          }}
        />
      ) : (
        <>
          <div>
            <div className="period-label">{period.label}</div>
            <div className="period-dates">
              {formatPeriodDates(period.period_start, period.period_end)} · {days} days
            </div>
          </div>
          <div className="period-status">
            {record ? (
              <span className="pill pill-sound">
                <Icon name="check" />
                Entered (revision {record.revision})
              </span>
            ) : (
              <span className="pill pill-muted">
                <Icon name="minus" />
                Not entered
              </span>
            )}
            {record?.created_by_email && (
              <span className="note">Entered by {record.created_by_email}</span>
            )}
            <div className="actions-cell">
              <button
                type="button"
                className="button button-small button-quiet"
                onClick={() => setEditing(true)}
                aria-label={`Edit period ${period.label}`}
              >
                <Icon name="calendar" />
                Edit period
              </button>
              {canDelete && (
                <button
                  type="button"
                  className="button button-small button-quiet button-danger-quiet"
                  onClick={() => setConfirming(true)}
                  aria-label={`Delete period ${period.label}`}
                >
                  <Icon name="trash" />
                  Delete
                </button>
              )}
              <Link className="button button-small button-quiet" to={`/periods/${period.id}/data`}>
                <Icon name="edit" />
                {record ? 'Edit data' : 'Enter data'}
              </Link>
              {record && canViewDashboard && (
                <Link className="button button-small" to={`/periods/${period.id}/dashboard`}>
                  <Icon name="chart" />
                  Dashboard
                </Link>
              )}
            </div>
          </div>
        </>
      )}

      {confirming && (
        <ConfirmDialog
          title={`Delete ${period.label}?`}
          confirmLabel="Delete period"
          busyLabel="Deleting…"
          busy={remove.isPending}
          error={remove.isError ? remove.error.message : null}
          onCancel={() => {
            remove.reset();
            setConfirming(false);
          }}
          onConfirm={() => remove.mutate()}
        >
          <p>
            This permanently deletes the reporting period{' '}
            <strong>
              {period.label} ({formatPeriodDates(period.period_start, period.period_end)})
            </strong>
            {record
              ? ', its financial data and every earlier revision of it, including any imported trial balance.'
              : '. No financial data has been entered for it.'}
          </p>
          <p className="muted">This cannot be undone.</p>
        </ConfirmDialog>
      )}
    </div>
  );
}
