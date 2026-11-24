import { Link } from 'react-router-dom';

import Icon from './Icon.jsx';
import { formatAmount } from '../utils/format.js';

/**
 * How far an assessment can be relied on: Validated, Provisional or
 * Insufficient data. Deliberately not the Sound / Vulnerable / Distressed
 * pill: this describes the data, not the company.
 */
// "validated" is shown as "Checks passed": the figures passed the checks
// below, which is not the same as being audited or known to be complete.
export const ASSESSMENT_STATUS = {
  validated: { label: 'Checks passed', icon: 'check' },
  provisional: { label: 'Provisional', icon: 'alert' },
  insufficient_data: { label: 'Insufficient data', icon: 'minus' },
};

export function AssessmentStatusBadge({ status }) {
  const known = ASSESSMENT_STATUS[status];
  if (!known) return null;
  return (
    <span
      className={`reliability-badge reliability-${status}`}
      title={
        status === 'validated'
          ? 'The figures passed the consistency checks listed under "What was checked". They have not been audited.'
          : undefined
      }
    >
      <Icon name={known.icon} />
      <span className="reliability-badge-label">Data:</span> {known.label}
    </span>
  );
}

const CHECK_MARKS = { true: ['check', 'Passed'], false: ['cross', 'Failed'], null: ['minus', 'Not applicable'] };

/** Exactly what was verified, and what "checks passed" does not mean. */
export function ChecksPerformed({ checks }) {
  if (!checks?.length) return null;
  return (
    <details className="checks-performed">
      <summary>What was checked</summary>
      <ul>
        {checks.map((check) => {
          const [icon, word] = CHECK_MARKS[String(check.passed)];
          return (
            <li key={check.name} className={`check-${String(check.passed)}`}>
              <Icon name={icon} />
              <span>
                <strong>{check.name}</strong>
                <span className="visually-hidden"> — {word}.</span>
                <span className="note">{check.detail}</span>
              </span>
            </li>
          );
        })}
      </ul>
      <p className="note">
        These checks confirm that the figures are consistent with each other. They cannot
        detect an account that was left out altogether, or figures that are consistent but
        wrong; they are not an audit.
      </p>
    </details>
  );
}

/** Reported against calculated net profit, with the difference. */
export function ReconciliationFigures({ reconciliation, currency }) {
  if (!reconciliation) return null;
  const money = (value) => `${currency ? `${currency} ` : ''}${formatAmount(value)}`;
  return (
    <dl className="reconciliation-figures">
      <div>
        <dt>Reported net profit</dt>
        <dd>{money(reconciliation.reported_net_profit)}</dd>
      </div>
      <div>
        <dt>Calculated net profit</dt>
        <dd>{money(reconciliation.calculated_net_profit)}</dd>
      </div>
      <div className={reconciliation.reconciled ? '' : 'is-off'}>
        <dt>Difference</dt>
        <dd>{money(Math.abs(reconciliation.difference))}</dd>
      </div>
    </dl>
  );
}

/**
 * The banner a provisional or unassessable result must carry. A validated
 * assessment needs no banner; its badge says so.
 */
export function AssessmentStatusBanner({ assessment, currency, reviewTo }) {
  const status = assessment.assessment_status;
  if (!ASSESSMENT_STATUS[status] || status === 'validated') return null;
  const material = (assessment.data_quality_issues || []).filter(
    (issue) => issue.severity === 'material',
  );
  const reconciliation = assessment.income_statement_reconciliation;

  if (status === 'insufficient_data') {
    return (
      <section className="alert alert-error reliability-banner" role="alert">
        <h2>Insufficient Data — Financial health cannot be assessed</h2>
        <ul className="alert-list">
          {material.map((issue) => (
            <li key={issue.code + issue.message}>{issue.message}</li>
          ))}
        </ul>
        {reviewTo && (
          <Link className="button button-small" to={reviewTo}>
            <Icon name="edit" />
            Review financial data
          </Link>
        )}
      </section>
    );
  }

  return (
    <section className="alert alert-warning reliability-banner" role="alert">
      <h2>Provisional Assessment — Financial data requires review</h2>
      <p>
        The score below is calculated from figures that have unresolved problems, so it is
        indicative only. It becomes validated once the financial data is corrected.
      </p>
      <ul className="alert-list">
        {material.map((issue) => (
          <li key={issue.code + issue.message}>{issue.message}</li>
        ))}
      </ul>
      {reconciliation && !reconciliation.reconciled && (
        <ReconciliationFigures reconciliation={reconciliation} currency={currency} />
      )}
      {reviewTo && (
        <Link className="button button-small" to={reviewTo}>
          <Icon name="edit" />
          Review financial data
        </Link>
      )}
    </section>
  );
}
