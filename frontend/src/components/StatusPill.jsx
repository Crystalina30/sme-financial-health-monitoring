import { CLASSIFICATION_LABELS, STATUS_LABELS } from '../utils/format.js';
import Icon from './Icon.jsx';

// Each status has its own shape as well as its own colour, so it can be told
// apart without relying on colour.
const STATUS_ICONS = {
  sound: 'check',
  concern: 'alert',
  distress: 'cross',
  not_applicable: 'minus',
};

/** An indicator's threshold status: Sound, Concern, Distress or N/A. */
export default function StatusPill({ status }) {
  return (
    <span className={`pill pill-${status}`}>
      <Icon name={STATUS_ICONS[status]} />
      {STATUS_LABELS[status]}
    </span>
  );
}

// The overall classification maps onto the same three colours and shapes.
export const CLASSIFICATION_STATUS = {
  sound: 'sound',
  vulnerable: 'concern',
  distressed: 'distress',
  // Not a health judgement: there was nothing to score.
  insufficient_data: 'not_applicable',
};

/** The overall classification: Sound, Vulnerable or Distressed. */
export function ClassificationPill({ classification, className = 'pill' }) {
  const status = CLASSIFICATION_STATUS[classification];
  return (
    <span className={`${className} pill-${status}`}>
      <Icon name={STATUS_ICONS[status]} />
      {CLASSIFICATION_LABELS[classification]}
    </span>
  );
}
