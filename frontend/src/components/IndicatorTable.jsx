import { formatIndicatorValue, formatScore, STATUS_LABELS } from '../utils/format.js';

/**
 * All ten indicators with value, score, status, movement and the source of
 * the threshold each was judged against.
 */
export default function IndicatorTable({ indicators }) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Indicator</th>
            <th>Value</th>
            <th>Score</th>
            <th>Status</th>
            <th>Change</th>
            <th>Thresholds</th>
          </tr>
        </thead>
        <tbody>
          {indicators.map((indicator) => (
            <tr key={indicator.code}>
              <td>
                <span className="indicator-name">{indicator.display_name}</span>
                {indicator.note && <span className="note">{indicator.note}</span>}
              </td>
              <td>{formatIndicatorValue(indicator.value, indicator.unit)}</td>
              <td>{formatScore(indicator.score)}</td>
              <td>
                <span className={`pill pill-${indicator.status}`}>
                  {STATUS_LABELS[indicator.status]}
                </span>
              </td>
              <td>
                {indicator.change?.change_percent === null ||
                indicator.change?.change_percent === undefined ? (
                  <span className="muted">—</span>
                ) : (
                  <span
                    className={
                      indicator.change.is_unfavourable ? 'change-bad' : 'change-ok'
                    }
                  >
                    {indicator.change.change_percent > 0 ? '+' : ''}
                    {indicator.change.change_percent}%
                  </span>
                )}
              </td>
              <td className="threshold-cell">
                {indicator.threshold ? (
                  <>
                    <span>
                      Concern {indicator.threshold.concern_threshold} · Distress{' '}
                      {indicator.threshold.distress_threshold}
                    </span>
                    <span className="note">{indicator.threshold.source_reference}</span>
                  </>
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
