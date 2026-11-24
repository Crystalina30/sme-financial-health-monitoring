import { AssessmentStatusBadge } from './AssessmentStatus.jsx';
import ScoreRing from './ScoreRing.jsx';
import { CLASSIFICATION_STATUS, ClassificationPill } from './StatusPill.jsx';

/** Headline overall score, drawn as a ring, with its classification. */
export default function ScoreSummary({
  overallScore,
  classification,
  scoredCount,
  totalCount,
  assessmentStatus,
}) {
  return (
    <div className="score-summary">
      <ScoreRing
        score={overallScore}
        colour={`var(--${CLASSIFICATION_STATUS[classification]})`}
        size={168}
        stroke={12}
        large
      />
      {/* Financial health and data reliability are shown apart. */}
      <ClassificationPill classification={classification} className="score-band" />
      {assessmentStatus && <AssessmentStatusBadge status={assessmentStatus} />}
      <p className="note score-note">
        Equal-weighted mean of the applicable category scores
        {totalCount ? `, based on ${scoredCount} of ${totalCount} indicators` : ''}.
      </p>
    </div>
  );
}
