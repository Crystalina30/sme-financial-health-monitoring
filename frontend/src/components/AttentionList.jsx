import { ATTENTION_LABELS } from '../utils/format.js';
import Icon from './Icon.jsx';

const REASON_ICONS = {
  distress_breach: 'cross',
  concern_breach: 'alert',
  unfavourable_movement: 'trendDown',
};

/**
 * Indicators requiring attention, in priority order.
 *
 * Only indicators with a reason are listed; the full set is always available
 * in the indicator table below.
 */
export default function AttentionList({ attention }) {
  const flagged = attention.filter((item) => item.reason);

  if (flagged.length === 0) {
    return (
      <p className="muted">
        No indicator has breached a threshold or moved unfavourably since the previous
        reporting period.
      </p>
    );
  }

  return (
    <ol className="attention-list">
      {flagged.map((item) => (
        <li key={item.code} className={`attention-item attention-${item.reason}`}>
          <span className="attention-icon">
            <Icon name={REASON_ICONS[item.reason]} />
          </span>
          <span>
            <span className="attention-name">{item.display_name}</span>
            <span className="attention-reason">{ATTENTION_LABELS[item.reason]}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
