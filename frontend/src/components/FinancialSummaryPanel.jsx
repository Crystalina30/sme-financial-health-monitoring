import { useState } from 'react';

import { formatMoney } from '../utils/format.js';

const ROWS = [
  ['revenue', 'Revenue'],
  ['cost_of_goods_sold', 'Cost of goods sold'],
  ['gross_profit', 'Gross profit'],
  ['operating_expenses', 'Operating expenses'],
  ['operating_profit', 'Operating profit'],
  ['net_profit', 'Net profit'],
  ['total_assets', 'Total assets'],
  ['total_liabilities', 'Total liabilities'],
  ['total_equity', 'Total equity'],
];

function Amount({ value, currency }) {
  return (
    <>
      {currency && <span className="stat-currency">{currency}</span>}
      {formatMoney(value)}
    </>
  );
}

/** The accounts and formula behind one figure calculated from a trial balance. */
function FigureTrace({ label, figure, currency, onClose }) {
  return (
    <div className="figure-trace" role="region" aria-label={`How ${label} is calculated`}>
      <div className="figure-trace-header">
        <h3>{label}</h3>
        <button type="button" className="button button-small button-quiet" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="note">{figure.formula}</p>
      {figure.contributions.length ? (
        <table className="data-table figure-trace-table">
          <thead>
            <tr>
              <th scope="col">Account</th>
              <th scope="col">Source</th>
              <th scope="col" className="numeric">Effect</th>
            </tr>
          </thead>
          <tbody>
            {figure.contributions.map((item) => (
              <tr key={`${item.line_number}-${item.category}`}>
                <td>
                  {item.account_code && <span className="muted">{item.account_code} </span>}
                  {item.account_name}
                </td>
                <td className="muted">{item.source_ref || `Row ${item.line_number}`}</td>
                <td className="numeric">
                  {item.amount < 0 ? '−' : '+'}
                  {formatMoney(Math.abs(item.amount))}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={2}>{label}</th>
              <td className="numeric">
                <Amount value={figure.value} currency={currency} />
              </td>
            </tr>
          </tfoot>
        </table>
      ) : (
        <p className="muted">No account contributes to this figure.</p>
      )}
    </div>
  );
}

/**
 * Headline statement figures behind the assessment, one tile each.
 *
 * When the figures were calculated from a trial balance, `trace` holds each
 * figure's formula and contributing accounts, and every tile opens them.
 */
export default function FinancialSummaryPanel({ summary, currency, trace }) {
  const [open, setOpen] = useState(null);
  const openRow = ROWS.find(([key]) => key === open);

  return (
    <>
      <dl className="stat-grid summary-list">
        {ROWS.map(([key, label]) => {
          const value = (
            <dd className={summary[key] < 0 ? 'negative' : ''}>
              <Amount value={summary[key]} currency={currency} />
            </dd>
          );
          if (!trace?.[key]) {
            return (
              <div className="stat-tile" key={key}>
                <dt>{label}</dt>
                {value}
              </div>
            );
          }
          return (
            <div className={`stat-tile is-traceable${open === key ? ' is-open' : ''}`} key={key}>
              <dt>
                <button
                  type="button"
                  className="stat-trace-button"
                  aria-expanded={open === key}
                  onClick={() => setOpen(open === key ? null : key)}
                >
                  {label}
                </button>
              </dt>
              {value}
            </div>
          );
        })}
      </dl>
      {trace && openRow && (
        <FigureTrace
          label={openRow[1]}
          figure={trace[openRow[0]]}
          currency={currency}
          onClose={() => setOpen(null)}
        />
      )}
      {trace && !openRow && (
        <p className="note figure-trace-hint">
          Calculated from the trial balance. Click a figure to see the accounts behind it.
        </p>
      )}
    </>
  );
}
