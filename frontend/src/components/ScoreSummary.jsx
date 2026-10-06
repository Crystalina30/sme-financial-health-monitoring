import { CLASSIFICATION_LABELS, formatScore } from '../utils/format.js';
import { CLASSIFICATION_COLOURS } from '../charts/chartTheme.js';

/** Headline overall score and classification. */
export default function ScoreSummary({ overallScore, classification }) {
  const colour = CLASSIFICATION_COLOURS[classification];
  return (
    <div className="score-summary">
      <div className="score-value" style={{ color: colour }}>
        {formatScore(overallScore)}
        <span className="score-outof">/ 100</span>
      </div>
      <div className="score-band" style={{ backgroundColor: colour }}>
        {CLASSIFICATION_LABELS[classification]}
      </div>
      <p className="muted score-note">
        Equal-weighted mean of the applicable category scores.
      </p>
    </div>
  );
}
