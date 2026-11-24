import {
  CATEGORY_LABELS,
  CLASSIFICATION_BANDS,
  CLASSIFICATION_LABELS,
  formatIndicatorValue,
  formatScore,
  formatWeight,
  INDICATOR_FORMULAS,
} from '../utils/format.js';
import FlipCard from './FlipCard.jsx';
import ScoreRing from './ScoreRing.jsx';
import ScoreSummary from './ScoreSummary.jsx';
import StatusPill from './StatusPill.jsx';

const ANCHORS = [
  ['floor_value', 'Floor', 0],
  ['distress_threshold', 'Distress', 40],
  ['concern_threshold', 'Concern', 60],
  ['target_value', 'Target', 100],
];

/** A threshold in its small box: days are written "90 d" to fit. */
function formatAnchor(value, unit) {
  if (value === null || value === undefined) return '—';
  return unit === 'days' ? `${value.toFixed(0)} d` : formatIndicatorValue(value, unit);
}

function ChangeSinceLastPeriod({ change }) {
  if (change?.change_percent === null || change?.change_percent === undefined) {
    return <span className="muted">No previous period to compare</span>;
  }
  return (
    <span className={change.is_unfavourable ? 'change-bad' : 'change-ok'}>
      {change.change_percent > 0 ? '+' : ''}
      {change.change_percent}% since last period
    </span>
  );
}

/** One of the ten indicators: result on the front, calculation on the back. */
export function IndicatorCard({ indicator, periodDays }) {
  const { threshold, unit } = indicator;
  const usesPeriod = ['asset_turnover', 'days_sales_outstanding'].includes(indicator.code);

  return (
    <FlipCard
      label={indicator.display_name}
      className="indicator-card"
      front={
        <div className="indicator-front">
          <span className="card-kicker">{CATEGORY_LABELS[indicator.category]}</span>
          <h3>{indicator.display_name}</h3>
          <span className="indicator-value">{formatIndicatorValue(indicator.value, unit)}</span>
          <div className="indicator-front-row">
            <span className="indicator-score">
              Score <strong>{formatScore(indicator.score)}</strong>
            </span>
            <StatusPill status={indicator.status} />
          </div>
          {indicator.note ? (
            <span className="note">{indicator.note}</span>
          ) : (
            <span className="note">
              <ChangeSinceLastPeriod change={indicator.change} />
            </span>
          )}
        </div>
      }
      back={
        // Laid out to fit the card's own size, so turning it over never
        // changes its height. The threshold basis and source are in the
        // formula's tooltip.
        <div className="flip-back-content indicator-back">
          <div className="indicator-back-head">
            <h3>{indicator.display_name}</h3>
            <StatusPill status={indicator.status} />
          </div>
          <p
            className="indicator-back-formula"
            title={
              threshold?.basis
                ? `${threshold.basis.split(' Floor and target:')[0]} ${threshold.source_reference || ''}`.trim()
                : undefined
            }
          >
            <span className="visually-hidden">Formula: </span>
            {INDICATOR_FORMULAS[indicator.code]}
            {usesPeriod && <span className="muted"> (D = {periodDays} days)</span>}
          </p>
          <dl className="indicator-back-grid indicator-back-anchors" aria-label="Floor · Distress · Concern · Target">
            {ANCHORS.map(([key, name, score]) => (
              <div
                key={key}
                title={`${name}: ${threshold ? formatIndicatorValue(threshold[key], unit) : '—'} scores ${score}`}
              >
                <dt>{name}</dt>
                <dd>{threshold ? formatAnchor(threshold[key], unit) : '—'}</dd>
              </div>
            ))}
          </dl>
          <dl className="indicator-back-grid">
            <div>
              <dt>Value</dt>
              <dd>{formatIndicatorValue(indicator.value, unit)}</dd>
            </div>
            <div>
              <dt>Score</dt>
              <dd>{formatScore(indicator.score)}</dd>
            </div>
            <div>
              <dt>Weight</dt>
              <dd>{formatWeight(indicator.effective_weight)}</dd>
            </div>
          </dl>
        </div>
      }
    />
  );
}

/** A category: score ring on the front, how its average is made on the back. */
export function CategoryCard({ category, indicators, isWeakest }) {
  const name = CATEGORY_LABELS[category.category];
  const members = indicators.filter((item) => item.category === category.category);
  const scored = members.filter((item) => item.score !== null);

  return (
    <FlipCard
      label={name}
      className={`category-card${isWeakest ? ' is-weakest' : ''}`}
      front={
        <div className="category-front">
          <ScoreRing score={category.score} colour="var(--series)" size={84} stroke={8} />
          <div>
            <span className="category-name">
              {name}
              {isWeakest && <span className="weakest-badge">Weakest</span>}
            </span>
            <span className="category-count">
              {category.applicable_indicator_count}{' '}
              {category.applicable_indicator_count === 1 ? 'indicator' : 'indicators'} applicable
            </span>
          </div>
        </div>
      }
      back={
        <div className="flip-back-content">
          <h3>{name}</h3>
          <p className="formula">
            {scored.length
              ? `(${scored.map((item) => item.score.toFixed(2)).join(' + ')}) ÷ ${scored.length} = ${formatScore(category.score)}`
              : 'No indicator could be scored, so this category is left out of the overall score.'}
          </p>
          <ul className="calc-members">
            {members.map((item) => (
              <li key={item.code}>
                <span>{item.display_name}</span>
                <span className="numeric">{formatIndicatorValue(item.value, item.unit)}</span>
                <span className="numeric">{formatScore(item.score)}</span>
                <span className="numeric muted">{formatWeight(item.effective_weight)}</span>
              </li>
            ))}
          </ul>
        </div>
      }
    />
  );
}

/** The overall score: ring on the front, the final average and the bands on the back. */
export function OverallScoreCard({ assessment }) {
  const scored = assessment.category_scores.filter((item) => item.score !== null);

  return (
    <FlipCard
      label="the overall score"
      className="overall-card"
      front={
        <div>
          <h2>Overall score</h2>
          <ScoreSummary
            overallScore={assessment.overall_score}
            classification={assessment.classification}
            scoredCount={assessment.scored_indicator_count}
            totalCount={assessment.total_indicator_count}
            assessmentStatus={assessment.assessment_status}
          />
        </div>
      }
      back={
        <div className="flip-back-content">
          <h2>Overall score</h2>
          <p className="muted">The average of the scored categories, each counting equally:</p>
          <p className="formula">
            {scored.length
              ? `(${scored.map((item) => item.score.toFixed(2)).join(' + ')}) ÷ ${scored.length} = ${formatScore(assessment.overall_score)}`
              : 'No category could be scored, so there is no overall score.'}
          </p>
          <dl className="calc-list">
            {CLASSIFICATION_BANDS.map((band) => (
              <div key={band.classification}>
                <dt>{CLASSIFICATION_LABELS[band.classification]}</dt>
                <dd>{band.range}</dd>
              </div>
            ))}
          </dl>
          <p className="note calc-basis">
            Methodology {assessment.methodology_version}: OECD/JRC composite-indicator
            framework, equal weights, arithmetic mean. The 60/40 bands and the threshold
            values are project-defined and not yet validated against real outcomes. This
            describes current condition; it does not predict failure.
          </p>
        </div>
      }
    />
  );
}
