import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import AttentionList from '../components/AttentionList.jsx';
import { AssessmentStatusBanner, ChecksPerformed } from '../components/AssessmentStatus.jsx';
import FinancialSummaryPanel from '../components/FinancialSummaryPanel.jsx';
import Icon from '../components/Icon.jsx';
import { CategoryCard, IndicatorCard, OverallScoreCard } from '../components/ScoreCards.jsx';
import StatusPill from '../components/StatusPill.jsx';
import HealthScoreTrendChart from '../charts/HealthScoreTrendChart.jsx';
import IndicatorStatusChart from '../charts/IndicatorStatusChart.jsx';
import IndicatorTrendChart from '../charts/IndicatorTrendChart.jsx';
import { useBreadcrumbs } from '../context/BreadcrumbContext.jsx';
import { useOrganisation } from '../context/OrganisationContext.jsx';
import { api } from '../services/apiClient.js';

const STATUS_KEY = ['sound', 'concern', 'distress', 'not_applicable'];

export default function DashboardPage() {
  const { periodId } = useParams();
  const { companyId } = useOrganisation();
  const [trendIndicator, setTrendIndicator] = useState('current_ratio');

  const dashboard = useQuery({
    queryKey: ['dashboard', companyId, periodId],
    queryFn: () => api.getDashboard(companyId, periodId),
  });
  const company = useQuery({
    queryKey: ['company', companyId],
    queryFn: () => api.getCompany(companyId),
  });
  // When the period's figures came from a trial balance, fetch it so every
  // summary figure can be traced to the accounts that make it up.
  const records = useQuery({
    queryKey: ['records', companyId],
    queryFn: () => api.listRecords(companyId),
  });
  const record = records.data?.find((item) => item.reporting_period_id === Number(periodId));
  const trialBalance = useQuery({
    queryKey: ['trial-balance', record?.id],
    queryFn: () => api.getTrialBalance(record.id),
    enabled: record?.source === 'trial_balance',
  });

  const periodLabel = dashboard.data?.assessment.period_label;
  useBreadcrumbs([
    { label: 'Financial Overview', to: '/overview' },
    { label: periodLabel || 'Period', to: '/history' },
    { label: 'Financial Analysis' },
  ]);

  if (dashboard.isLoading) return <div className="page centred-message">Loading dashboard…</div>;
  if (dashboard.isError) {
    return (
      <div className="page">
        <p className="alert alert-error">{dashboard.error.message}</p>
        <Link className="button button-quiet" to="/history">
          Back to company
        </Link>
      </div>
    );
  }

  const { assessment, financial_summary: summary, score_trend: trend } = dashboard.data;

  // Indicators in attention order, so the ones needing attention lead.
  const attentionOrder = new Map(
    assessment.attention.map((item, index) => [item.code, index]),
  );
  const orderedIndicators = [...assessment.indicators].sort(
    (a, b) => attentionOrder.get(a.code) - attentionOrder.get(b.code),
  );

  const selected = assessment.indicators.find(
    (indicator) => indicator.code === trendIndicator,
  );

  // The indicator trend uses the periods already on the dashboard payload;
  // only the current period's value is plotted for the selected indicator,
  // which is honest about what one request can show.
  const indicatorTrendPoints = [
    { label: assessment.period_label, value: selected?.value ?? null },
  ];

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <h1>Financial health</h1>
          <p className="page-subtitle">
            {company.data?.name ? `${company.data.name} · ` : ''}
            {assessment.period_label}
          </p>
        </div>
        <div className="page-actions">
          <Link
            className="button button-small button-quiet"
            to={`/periods/${periodId}/data`}
          >
            <Icon name="edit" />
            Edit financial data
          </Link>
        </div>
      </div>

      {/* Material problems: the assessment is provisional or impossible. */}
      <AssessmentStatusBanner
        assessment={assessment}
        currency={company.data?.currency_code}
        reviewTo={`/periods/${periodId}/data`}
      />
      <ChecksPerformed checks={assessment.checks_performed} />
      {assessment.data_quality_notes.length > 0 && (
        <div className="alert alert-warning" role="note">
          <strong>Points that affect how far this score can be relied on:</strong>
          <ul className="alert-list">
            {assessment.data_quality_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="dashboard-grid">
        <section className="card dash-score reveal">
          <OverallScoreCard assessment={assessment} />
        </section>

        <section className="card dash-categories reveal" style={{ '--i': 1 }}>
          <div className="card-header">
            <h2>Category scores</h2>
            <span className="note">Click a card to see how it is calculated</span>
          </div>
          <div className="category-grid">
            {assessment.category_scores.map((item) => (
              <CategoryCard
                key={item.category}
                category={item}
                indicators={assessment.indicators}
                isWeakest={item.category === assessment.robustness.weakest_category}
              />
            ))}
          </div>
        </section>

        <section className="card dash-attention reveal" style={{ '--i': 2 }}>
          <h2>Requiring attention</h2>
          <AttentionList attention={assessment.attention} />
        </section>

        <section className="card dash-summary reveal" style={{ '--i': 3 }}>
          <div className="card-header">
            <h2>Financial summary</h2>
            {company.data && <span className="note">Figures in {company.data.currency_code}</span>}
          </div>
          <FinancialSummaryPanel
            summary={summary}
            currency={company.data?.currency_code}
            trace={trialBalance.data?.derivation.figures}
          />
        </section>

        <section className="card dash-indicators reveal" style={{ '--i': 4 }}>
          <div className="card-header">
            <h2>Indicators</h2>
            <span className="note">Click a card to see its formula, thresholds and weight</span>
          </div>
          <div className="indicator-grid">
            {orderedIndicators.map((indicator) => (
              <IndicatorCard
                key={indicator.code}
                indicator={indicator}
                periodDays={assessment.period_days}
              />
            ))}
          </div>
        </section>

        <section className="card dash-status reveal" style={{ '--i': 4 }}>
          <div className="card-header">
            <h2>Indicator scores by status</h2>
            <div className="company-meta" aria-label="Status key">
              {STATUS_KEY.map((status) => (
                <StatusPill key={status} status={status} />
              ))}
            </div>
          </div>
          <IndicatorStatusChart indicators={orderedIndicators} />
        </section>

        <section className="card dash-score-trend reveal" style={{ '--i': 5 }}>
          <div className="card-header">
            <h2>Health score trend</h2>
            {trend.some((point) => point.assessment_status !== 'validated') && (
              <span className="note">Hollow points are provisional</span>
            )}
          </div>
          {trend.length > 1 ? (
            <HealthScoreTrendChart trend={trend} />
          ) : (
            <p className="empty-state">
              Enter financial data for a second reporting period to see a trend.
            </p>
          )}
        </section>

        <section className="card dash-indicator-trend reveal" style={{ '--i': 6 }}>
          <div className="card-header">
            <h2>Indicator trend</h2>
            <div className="trend-controls">
              <label htmlFor="trend-indicator" className="inline-label">
                Indicator
              </label>
              <select
                id="trend-indicator"
                value={trendIndicator}
                onChange={(event) => setTrendIndicator(event.target.value)}
              >
                {assessment.indicators.map((indicator) => (
                  <option key={indicator.code} value={indicator.code}>
                    {indicator.display_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <IndicatorTrendChart
            points={indicatorTrendPoints}
            threshold={selected?.threshold}
            indicatorName={selected?.display_name}
          />
        </section>
      </div>
    </div>
  );
}
