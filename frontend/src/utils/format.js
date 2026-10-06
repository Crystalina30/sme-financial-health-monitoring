/** Display formatting shared by the dashboard components. */

export function formatIndicatorValue(value, unit) {
  if (value === null || value === undefined) return 'N/A';
  switch (unit) {
    case 'percent':
      return `${value.toFixed(1)}%`;
    case 'days':
      return `${value.toFixed(0)} days`;
    case 'times':
      return `${value.toFixed(2)}×`;
    default:
      return value.toFixed(2);
  }
}

export function formatMoney(value) {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-MY', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatScore(score) {
  return score === null || score === undefined ? 'N/A' : score.toFixed(1);
}

export const STATUS_LABELS = {
  sound: 'Sound',
  concern: 'Concern',
  distress: 'Distress',
  not_applicable: 'N/A',
};

export const CLASSIFICATION_LABELS = {
  sound: 'Sound',
  vulnerable: 'Vulnerable',
  distressed: 'Distressed',
};

export const ATTENTION_LABELS = {
  distress_breach: 'Distress threshold breached',
  concern_breach: 'Concern threshold breached',
  unfavourable_movement: 'Unfavourable movement since last period',
};

export const CATEGORY_LABELS = {
  liquidity: 'Liquidity',
  profitability: 'Profitability',
  solvency: 'Solvency',
  efficiency: 'Efficiency',
};
