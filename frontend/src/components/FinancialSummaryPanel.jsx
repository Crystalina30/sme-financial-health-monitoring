import { formatMoney } from '../utils/format.js';

const ROWS = [
  ['revenue', 'Revenue'],
  ['gross_profit', 'Gross profit'],
  ['operating_profit', 'Operating profit'],
  ['net_profit', 'Net profit'],
  ['total_assets', 'Total assets'],
  ['total_liabilities', 'Total liabilities'],
  ['total_equity', 'Total equity'],
];

/** Headline statement figures behind the assessment. */
export default function FinancialSummaryPanel({ summary }) {
  return (
    <dl className="summary-list">
      {ROWS.map(([key, label]) => (
        <div className="summary-row" key={key}>
          <dt>{label}</dt>
          <dd className={summary[key] < 0 ? 'negative' : ''}>{formatMoney(summary[key])}</dd>
        </div>
      ))}
    </dl>
  );
}
