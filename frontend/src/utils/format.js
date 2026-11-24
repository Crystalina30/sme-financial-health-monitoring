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

const DATE_FORMAT = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
});

function utcDate(isoDate) {
  return new Date(`${isoDate}T00:00:00Z`);
}

/** "1 Jan 2025" from "2025-01-01". */
export function formatDate(isoDate) {
  return DATE_FORMAT.format(utcDate(isoDate));
}

export function formatPeriodDates(start, end) {
  return `${formatDate(start)} – ${formatDate(end)}`;
}

/** Days covered, counting both the first and last day (as the backend does). */
export function periodLengthDays(start, end) {
  if (!start || !end) return 0;
  return Math.round((utcDate(end) - utcDate(start)) / 86400000) + 1;
}

/** Roughly a year, leap years included (the backend's 360-370 day rule). */
export function isFullYear(days) {
  return days >= 360 && days <= 370;
}

/** The day before the same date next year: a one-year period's end. */
export function oneYearEnd(isoStart) {
  const date = utcDate(isoStart);
  date.setUTCFullYear(date.getUTCFullYear() + 1);
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}

/** An amount to the cent, e.g. "109,999.99". */
export function formatAmount(value) {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-MY', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/** A typed amount as whole cents, so sums are exact (no floating-point drift). */
export function toCents(value) {
  return Math.round(Number(value || 0) * 100);
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
  insufficient_data: 'Insufficient data',
};

/** Classification bands, as defined in the backend scoring service. */
export const CLASSIFICATION_BANDS = [
  { classification: 'sound', range: '60–100' },
  { classification: 'vulnerable', range: '40–59.99' },
  { classification: 'distressed', range: 'Below 40' },
  { classification: 'insufficient_data', range: 'No indicator could be scored' },
];

/** How each indicator is calculated, as implemented in the backend engine. */
export const INDICATOR_FORMULAS = {
  current_ratio: 'Current assets ÷ Current liabilities',
  quick_ratio: '(Current assets − Inventory) ÷ Current liabilities',
  gross_profit_margin: 'Gross profit ÷ Revenue × 100',
  net_profit_margin: 'Net profit ÷ Revenue × 100',
  return_on_assets: 'Net profit ÷ Total assets × 100',
  debt_to_equity: 'Total liabilities ÷ Total equity',
  debt_ratio: 'Total liabilities ÷ Total assets',
  interest_coverage: 'Operating profit ÷ Interest expense',
  asset_turnover: '(Revenue × 365 ÷ D) ÷ Total assets',
  days_sales_outstanding: 'Accounts receivable ÷ Revenue × D',
};

/** Format a weight as a percentage: 0.125 as "12.5%", 1/12 as "8.33%". */
export function formatWeight(weight) {
  if (weight === null || weight === undefined) return '—';
  const percent = weight * 100;
  const exactToOneDecimal = Math.abs(percent * 10 - Math.round(percent * 10)) < 1e-9;
  return `${percent.toFixed(exactToOneDecimal ? 1 : 2)}%`;
}

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
