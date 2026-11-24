import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { AssessmentStatusBadge } from '../components/AssessmentStatus.jsx';
import Icon from '../components/Icon.jsx';
import ScoreSummary from '../components/ScoreSummary.jsx';
import { ClassificationPill } from '../components/StatusPill.jsx';
import { useBreadcrumbs } from '../context/BreadcrumbContext.jsx';
import { api } from '../services/apiClient.js';
import { CATEGORY_LABELS, formatMoney, formatScore } from '../utils/format.js';

const DATE_FORMAT = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});

function formatDate(value) {
  return DATE_FORMAT.format(new Date(`${value}T00:00:00`));
}

function periodDates(period) {
  return `${formatDate(period.period_start)} – ${formatDate(period.period_end)}`;
}

/** A period of roughly a year needs no comment; anything else is worth saying. */
function isUnusualLength(period) {
  return period.period_days < 360 || period.period_days > 370;
}

function PeriodStatus({ period }) {
  if (period.status === 'no_data') return <span className="muted">No financial data</span>;
  return <ClassificationPill classification={period.classification} />;
}

function SummaryTile({ label, children, note }) {
  return (
    <div className="stat-tile overview-tile">
      <dt>{label}</dt>
      <dd>{children}</dd>
      {note && <span className="note">{note}</span>}
    </div>
  );
}

function CategoryBars({ categories }) {
  return (
    <ul className="overview-categories">
      {categories.map((category) => {
        const score = category.score;
        return (
          <li key={category.category}>
            <div className="overview-category-head">
              <span>{CATEGORY_LABELS[category.category]}</span>
              <strong>{formatScore(score)}</strong>
            </div>
            <div
              className="overview-bar"
              role="meter"
              aria-label={`${CATEGORY_LABELS[category.category]} score`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={score ?? undefined}
              aria-valuetext={score === null ? 'Not applicable' : `${score.toFixed(1)} out of 100`}
            >
              <span style={{ width: `${score ?? 0}%` }} />
            </div>
            <span className="note">
              {score === null
                ? 'No indicator could be scored'
                : `${category.applicable_indicator_count} ${
                    category.applicable_indicator_count === 1 ? 'indicator' : 'indicators'
                  } scored`}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function QuickActions({ latest, latestAssessed }) {
  const dataPath = latest ? `/periods/${latest.id}/data` : null;
  const actions = [
    {
      label: 'Import trial balance',
      icon: 'upload',
      to: dataPath ? `${dataPath}?mode=trial_balance` : '/history',
      hint: latest ? `For ${latest.label}` : 'Create a reporting period first',
    },
    {
      label: 'Enter statement totals',
      icon: 'edit',
      to: dataPath ? `${dataPath}?mode=statement` : '/history',
      hint: latest ? `For ${latest.label}` : 'Create a reporting period first',
    },
    {
      label: 'View financial analysis',
      icon: 'analysis',
      to: latestAssessed ? `/periods/${latestAssessed.id}/dashboard` : null,
      hint: latestAssessed ? latestAssessed.label : 'No assessed period yet',
    },
    { label: 'View financial history', icon: 'history', to: '/history', hint: 'All periods' },
    {
      label: 'Manage reporting periods',
      icon: 'calendar',
      to: '/history',
      hint: 'Add or open a period',
    },
  ];
  return (
    <ul className="quick-actions">
      {actions.map((action) => (
        <li key={action.label}>
          {action.to ? (
            <Link className="quick-action" to={action.to}>
              <Icon name={action.icon} />
              <span>
                <strong>{action.label}</strong>
                <span className="note">{action.hint}</span>
              </span>
            </Link>
          ) : (
            <span className="quick-action is-disabled" aria-disabled="true">
              <Icon name={action.icon} />
              <span>
                <strong>{action.label}</strong>
                <span className="note">{action.hint}</span>
              </span>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function HistoryPreview({ periods }) {
  return (
    <div className="table-scroll">
      <table className="data-table overview-history">
        <thead>
          <tr>
            <th scope="col">Reporting period</th>
            <th scope="col">Dates</th>
            <th scope="col" className="numeric">Overall score</th>
            <th scope="col">Classification</th>
            <th scope="col">Data</th>
          </tr>
        </thead>
        <tbody>
          {periods.map((period) => (
            <tr key={period.id}>
              <th scope="row">
                {period.status === 'no_data' ? (
                  period.label
                ) : (
                  <Link to={`/periods/${period.id}/dashboard`}>{period.label}</Link>
                )}
              </th>
              <td className="muted">
                {periodDates(period)}
                {isUnusualLength(period) && <span className="note">{period.period_days} days</span>}
              </td>
              <td className="numeric">{formatScore(period.overall_score)}</td>
              <td>
                <PeriodStatus period={period} />
              </td>
              <td>
                {period.status === 'no_data' && (
                  <Link to={`/periods/${period.id}/data`}>Add data</Link>
                )}
                {period.status !== 'no_data' && (
                  <>
                    <AssessmentStatusBadge status={period.assessment_status} />
                    <span className="note">
                      {period.record.source === 'trial_balance'
                        ? 'From a trial balance'
                        : 'Statement totals'}
                    </span>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function OverviewPage() {
  const overview = useQuery({ queryKey: ['overview'], queryFn: api.getOverview });
  useBreadcrumbs([{ label: 'Financial Overview' }]);

  if (overview.isLoading) return <div className="page centred-message">Loading overview…</div>;
  if (overview.isError) {
    return (
      <div className="page">
        <p className="alert alert-error">{overview.error.message}</p>
      </div>
    );
  }

  const { organisation, periods, latest_period_id: latestId } = overview.data;
  const latest = periods.find((period) => period.id === latestId);
  const latestAssessed = periods.find(
    (period) => period.id === overview.data.latest_assessed_period_id,
  );
  // The newest period with a record, even if nothing could be scored in it.
  const latestWithData = periods.find((period) => period.status !== 'no_data');

  return (
    <div className="page overview-page">
      <header className="overview-header reveal">
        <div>
          <span className="card-kicker">Financial overview</span>
          <h1>{organisation.name}</h1>
          <ul className="overview-tags" aria-label="Organisation details">
            <li>{organisation.industry || 'Industry not recorded'}</li>
            <li>{organisation.currency_code}</li>
            {latest && (
              <li>
                Latest period: <strong>{latest.label}</strong> ({periodDates(latest)})
              </li>
            )}
          </ul>
        </div>
      </header>

      {periods.length === 0 && (
        <section className="card reveal empty-state overview-empty">
          <h2>No financial data available</h2>
          <p>
            Create a reporting period, then import its trial balance or enter its statement
            totals to see {organisation.name}&rsquo;s financial health.
          </p>
          <Link className="button" to="/history">
            <Icon name="plus" />
            Create a reporting period
          </Link>
        </section>
      )}

      {periods.length > 0 && !latestWithData && (
        <section className="card reveal empty-state overview-empty">
          <h2>No financial data available</h2>
          <p>
            {latest.label} has no financial data yet. Import a trial balance or enter statement
            totals to calculate a financial health score.
          </p>
          <Link className="button" to={`/periods/${latest.id}/data`}>
            <Icon name="upload" />
            Add financial data
          </Link>
        </section>
      )}

      {latestWithData && (
        <>
          {latest && latest.id !== latestWithData.id && (
            <p className="alert alert-info">
              {latest.label} has no financial data yet, so the figures below are from{' '}
              {latestWithData.label}.
            </p>
          )}
          {latestWithData.data_quality_warnings.length > 0 && (
            <div
              className={`alert ${
                latestWithData.assessment_status === 'validated' ? 'alert-info' : 'alert-warning'
              } overview-quality`}
              role="status"
            >
              <strong>
                {latestWithData.assessment_status === 'provisional' &&
                  `Provisional Assessment — Financial data for ${latestWithData.label} requires review.`}
                {latestWithData.assessment_status === 'insufficient_data' &&
                  'Insufficient Data — Financial health cannot be assessed.'}
                {latestWithData.assessment_status === 'validated' &&
                  `Notes on the data for ${latestWithData.label}:`}
              </strong>
              <ul className="alert-list">
                {latestWithData.data_quality_warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}

          <section className="card reveal overview-summary" style={{ '--i': 1 }}>
            <div className="overview-score">
              <span className="card-kicker">Financial health score</span>
              <ScoreSummary
                overallScore={latestWithData.overall_score}
                classification={latestWithData.classification}
                scoredCount={latestWithData.scored_indicator_count}
                totalCount={latestWithData.total_indicator_count}
                assessmentStatus={latestWithData.assessment_status}
              />
            </div>
            <dl className="stat-grid overview-stats">
              <SummaryTile label="Classification">
                <ClassificationPill classification={latestWithData.classification} />
              </SummaryTile>
              <SummaryTile label="Total revenue">
                <span className="stat-currency">{organisation.currency_code}</span>
                {formatMoney(latestWithData.revenue)}
              </SummaryTile>
              <SummaryTile label="Net profit">
                <span className={latestWithData.net_profit < 0 ? 'negative' : ''}>
                  <span className="stat-currency">{organisation.currency_code}</span>
                  {formatMoney(latestWithData.net_profit)}
                </span>
              </SummaryTile>
              <SummaryTile
                label="Reporting period"
                note={`${periodDates(latestWithData)}${
                  isUnusualLength(latestWithData) ? ` · ${latestWithData.period_days} days` : ''
                }`}
              >
                {latestWithData.label}
              </SummaryTile>
            </dl>
          </section>
        </>
      )}

      <div className={`overview-grid${latestWithData ? '' : ' is-single'}`}>
        {latestWithData && (
          <section className="card reveal" style={{ '--i': 2 }}>
            <div className="card-header">
              <h2>Financial health by category</h2>
              <span className="note">{latestWithData.label}</span>
            </div>
            <CategoryBars categories={latestWithData.category_scores} />
          </section>
        )}

        <section className="card reveal" style={{ '--i': 3 }}>
          <div className="card-header">
            <h2>Quick actions</h2>
          </div>
          <QuickActions latest={latest} latestAssessed={latestAssessed} />
        </section>
      </div>

      {periods.length > 0 && (
        <section className="card reveal" style={{ '--i': 4 }}>
          <div className="card-header">
            <h2>Financial history</h2>
            <Link className="button button-small button-quiet" to="/history">
              View all periods
              <Icon name="arrowRight" />
            </Link>
          </div>
          <HistoryPreview periods={periods.slice(0, 5)} />
        </section>
      )}
    </div>
  );
}
