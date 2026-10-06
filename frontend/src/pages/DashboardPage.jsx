import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import AttentionList from '../components/AttentionList.jsx';
import FinancialSummaryPanel from '../components/FinancialSummaryPanel.jsx';
import IndicatorTable from '../components/IndicatorTable.jsx';
import ScoreSummary from '../components/ScoreSummary.jsx';
import CategoryScoreChart from '../charts/CategoryScoreChart.jsx';
import HealthScoreTrendChart from '../charts/HealthScoreTrendChart.jsx';
import IndicatorStatusChart from '../charts/IndicatorStatusChart.jsx';
import IndicatorTrendChart from '../charts/IndicatorTrendChart.jsx';
import { api } from '../services/apiClient.js';
import { CATEGORY_LABELS, formatScore } from '../utils/format.js';

export default function DashboardPage() {
  const { companyId, periodId } = useParams();
  const [trendIndicator, setTrendIndicator] = useState('current_ratio');

  const dashboard = useQuery({
    queryKey: ['dashboard', companyId, periodId],
    queryFn: () => api.getDashboard(companyId, periodId),
  });

  if (dashboard.isLoading) return <div className="page muted">Loading dashboard…</div>;
  if (dashboard.isError) {
    return (
      <div className="page">
        <p className="alert alert-error">{dashboard.error.message}</p>
        <Link className="button" to={`/companies/${companyId}`}>
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
      <p className="breadcrumb">
        <Link to="/companies">Companies</Link> /{' '}
        <Link to={`/companies/${companyId}`}>Company</Link> / {assessment.period_label}
      </p>

      <div className="page-heading">
        <h1>Financial health — {assessment.period_label}</h1>
        <Link
          className="button button-small button-quiet"
          to={`/companies/${companyId}/periods/${periodId}/data`}
        >
          Edit financial data
        </Link>
      </div>

      {!assessment.accounting_identity_ok && (
        <p className="alert alert-error">
          This record did not satisfy the accounting identity. {assessment.validation_notes}
        </p>
      )}
      {assessment.accounting_identity_ok && assessment.validation_notes && (
        <p className="alert alert-warning">{assessment.validation_notes}</p>
      )}

      <div className="dashboard-grid">
        <section className="card span-4">
          <h2>Overall score</h2>
          <ScoreSummary
            overallScore={assessment.overall_score}
            classification={assessment.classification}
          />
        </section>

        <section className="card span-8">
          <h2>Category scores</h2>
          <CategoryScoreChart categoryScores={assessment.category_scores} />
          <div className="category-figures">
            {assessment.category_scores.map((item) => (
              <div key={item.category}>
                <span className="category-name">{CATEGORY_LABELS[item.category]}</span>
                <span className="category-score">{formatScore(item.score)}</span>
                <span className="note">
                  {item.applicable_indicator_count} applicable
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="card span-5">
          <h2>Requiring attention</h2>
          <AttentionList attention={assessment.attention} />
        </section>

        <section className="card span-7">
          <h2>Indicator scores by status</h2>
          <IndicatorStatusChart indicators={orderedIndicators} />
        </section>

        <section className="card span-6">
          <h2>Health score trend</h2>
          {trend.length > 1 ? (
            <HealthScoreTrendChart trend={trend} />
          ) : (
            <p className="muted">
              Enter financial data for a second reporting period to see a trend.
            </p>
          )}
        </section>

        <section className="card span-6">
          <h2>Indicator trend</h2>
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
          <IndicatorTrendChart
            points={indicatorTrendPoints}
            threshold={selected?.threshold}
            indicatorName={selected?.display_name}
          />
        </section>

        <section className="card span-4">
          <h2>Financial summary</h2>
          <FinancialSummaryPanel summary={summary} />
        </section>

        <section className="card span-8">
          <h2>All indicators</h2>
          <IndicatorTable indicators={orderedIndicators} />
        </section>
      </div>
    </div>
  );
}
