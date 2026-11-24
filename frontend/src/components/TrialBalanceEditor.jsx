import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';

import Icon from './Icon.jsx';
import { api } from '../services/apiClient.js';
import { formatMoney } from '../utils/format.js';

/** The statement figures calculated from the trial balance, in statement order. */
const FIGURE_GROUPS = [
  {
    title: 'Income statement',
    figures: [
      ['revenue', 'Revenue'],
      ['cost_of_goods_sold', 'Cost of goods sold'],
      ['other_operating_income', 'Other operating income'],
      ['operating_expenses', 'Operating expenses'],
      ['other_income', 'Other income (non-operating)'],
      ['other_expenses', 'Other expenses (non-operating)'],
      ['interest_expense', 'Interest expense'],
      ['gross_profit', 'Gross profit'],
      ['operating_profit', 'Operating profit'],
      ['tax_expense', 'Tax expense'],
      ['net_profit', 'Net profit'],
    ],
  },
  {
    title: 'Balance sheet',
    figures: [
      ['cash_and_equivalents', 'Cash and equivalents'],
      ['accounts_receivable', 'Accounts receivable'],
      ['inventory', 'Inventory'],
      ['other_current_assets', 'Other current assets'],
      ['current_assets', 'Current assets'],
      ['non_current_assets', 'Non-current assets'],
      ['total_assets', 'Total assets'],
      ['current_liabilities', 'Current liabilities'],
      ['non_current_liabilities', 'Non-current liabilities'],
      ['total_liabilities', 'Total liabilities'],
      ['total_equity', 'Total equity'],
      ['retained_earnings', 'Retained earnings'],
    ],
  },
];

const SUGGESTION_NOTES = {
  previous_period: 'as last period',
  account_group: 'from its group',
  account_name: 'from its name',
  file: 'from the file',
};

let nextId = 1;
function newRow(values = {}) {
  nextId += 1;
  return {
    id: nextId,
    account_code: '',
    account_name: '',
    debit: '',
    credit: '',
    category: '',
    account_group: '',
    source_ref: '',
    suggestion: null,
    ...values,
  };
}

function toAmount(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number : 0;
}

function isBlank(row) {
  return !row.account_code && !row.account_name && !toAmount(row.debit) && !toAmount(row.credit);
}

/** Wait until the rows stop changing before recalculating. */
function useDebounced(value, delay) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return settled;
}

function DerivedFigure({ label, figure, currency }) {
  if (!figure) return null;
  const notReported = figure.value === null;
  return (
    <details className="derived-figure">
      <summary>
        <span>{label}</span>
        <strong>{notReported ? 'Not reported' : formatMoney(figure.value)}</strong>
      </summary>
      <p className="note">{figure.formula}</p>
      {figure.contributions.length > 0 && (
        <ul className="derived-accounts">
          {figure.contributions.map((item) => (
            <li key={`${item.line_number}-${item.category}`} title={item.source_ref || undefined}>
              <span className="muted">{item.account_code || `Row ${item.line_number}`}</span>
              <span>
                {item.account_name}
                {item.source_ref && <span className="note">{item.source_ref}</span>}
              </span>
              <span className="numeric">
                {item.amount < 0 ? '−' : '+'}
                {formatMoney(Math.abs(item.amount))}
              </span>
            </li>
          ))}
        </ul>
      )}
      {currency && <span className="note">Amounts in {currency}</span>}
    </details>
  );
}

const ADJUSTMENT_REF = 'Period-end adjustment';

/**
 * How stock is accounted for, and, when the closing count is missing, a way
 * to add it. Nothing is assumed: the count (or an explicit "no stock")
 * becomes visible adjustment rows that are saved with the trial balance.
 */
function InventoryPanel({ inventory, currency, onAdjust }) {
  const [count, setCount] = useState('');
  const today = new Date().toISOString().slice(0, 10);

  function adjustmentRows(amount) {
    const ref = amount
      ? `${ADJUSTMENT_REF}: closing stock count of ${amount.toFixed(2)} entered by user on ${today}`
      : `${ADJUSTMENT_REF}: no closing stock, confirmed by user on ${today}`;
    const rows = [];
    const opening = inventory.opening_balance_in_inventory;
    if (opening) {
      // The inventory account still holds opening stock: move it to cost of sales.
      const name = 'Opening stock transferred to cost of sales (period-end adjustment)';
      rows.push(newRow({ account_name: name, debit: String(opening), category: 'cost_of_sales', source_ref: ref }));
      rows.push(newRow({ account_name: name, credit: String(opening), category: 'inventory', source_ref: ref }));
    }
    if (amount) {
      const name = 'Closing stock (period-end adjustment)';
      rows.push(newRow({ account_name: name, debit: String(amount), category: 'inventory', source_ref: ref }));
      rows.push(newRow({ account_name: name, credit: String(amount), category: 'cost_of_sales', source_ref: ref }));
    } else {
      rows.push(newRow({
        account_name: 'Closing stock (period-end adjustment: confirmed nil)',
        category: 'cost_of_sales',
        source_ref: ref,
      }));
    }
    return rows;
  }

  return (
    <div className="tb-inventory" aria-label="Period-end stock">
      <h3>Period-end stock: {inventory.label}</h3>
      <p className="note">{inventory.explanation}</p>
      {inventory.needs_review && (
        <>
          <p className="note">
            An accountant should check this mapping. Recategorise the purchases (to inventory,
            if stock is kept perpetually), or confirm that purchases and cost of goods sold are
            separate costs; the confirmation is saved as an adjustment row with your name.
          </p>
          <button
            type="button"
            className="button button-small button-quiet"
            onClick={() =>
              onAdjust([
                newRow({
                  account_name: 'Cost of sales reviewed: separate costs (period-end adjustment)',
                  category: 'cost_of_sales',
                  source_ref: `${ADJUSTMENT_REF}: purchases and cost of goods sold confirmed as separate costs by user on ${today}`,
                }),
              ])
            }
          >
            Confirm they are separate costs
          </button>
        </>
      )}
      {inventory.needs_closing_stock && (
        <>
          <p className="note">
            Closing stock is not assumed to be zero. Enter the stock count at the period end, or
            confirm there was no stock. Either is added below as an adjustment row you can see and
            remove.
          </p>
          <div className="inline-form">
            <div className="field">
              <label htmlFor="closing-stock">Closing stock count{currency ? ` (${currency})` : ''}</label>
              <input
                id="closing-stock"
                type="number"
                min="0"
                step="0.01"
                value={count}
                onChange={(event) => setCount(event.target.value)}
              />
            </div>
            <button
              type="button"
              className="button button-small"
              disabled={!(Number(count) > 0)}
              onClick={() => onAdjust(adjustmentRows(Number(count)))}
            >
              Add closing stock
            </button>
            <button
              type="button"
              className="button button-small button-quiet"
              onClick={() => onAdjust(adjustmentRows(0))}
            >
              Confirm no closing stock
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default function TrialBalanceEditor({ companyId, periodId, existing, currency, onSaved }) {
  const [rows, setRows] = useState(() => [newRow(), newRow(), newRow()]);
  const [importMessage, setImportMessage] = useState(null);
  const [importErrors, setImportErrors] = useState([]);
  const [importWarnings, setImportWarnings] = useState([]);
  const [imported, setImported] = useState(null);
  const [importing, setImporting] = useState(false);
  const loadedFor = useRef(null);
  const fileInput = useRef(null);

  const categories = useQuery({
    queryKey: ['account-categories'],
    queryFn: api.listAccountCategories,
    staleTime: Infinity,
  });

  const stored = useQuery({
    queryKey: ['trial-balance', existing?.id],
    queryFn: () => api.getTrialBalance(existing.id),
    enabled: existing?.source === 'trial_balance',
  });

  // A correction starts from the trial balance already stored.
  useEffect(() => {
    if (!stored.data || loadedFor.current === stored.data.financial_record_id) return;
    loadedFor.current = stored.data.financial_record_id;
    setRows(
      stored.data.lines.map((line) =>
        newRow({
          account_code: line.account_code,
          account_name: line.account_name,
          debit: line.debit ? String(line.debit) : '',
          credit: line.credit ? String(line.credit) : '',
          category: line.category,
          account_group: line.account_group,
          source_ref: line.source_ref,
        }),
      ),
    );
  }, [stored.data]);

  const filled = rows.filter((row) => !isBlank(row));
  const unnamed = filled.filter((row) => !row.account_name.trim());
  const payloadLines = useMemo(
    () =>
      rows
        .filter((row) => !isBlank(row) && row.account_name.trim())
        .map((row) => ({
          account_code: row.account_code.trim(),
          account_name: row.account_name.trim(),
          debit: toAmount(row.debit),
          credit: toAmount(row.credit),
          category: row.category || null,
          account_group: row.account_group,
          source_ref: row.source_ref,
        })),
    [rows],
  );
  // Compared as text, so an unchanged trial balance is not recalculated.
  const payloadKey = JSON.stringify(payloadLines);
  const settledKey = useDebounced(payloadKey, 350);

  const preview = useQuery({
    queryKey: ['trial-balance-preview', settledKey],
    queryFn: () => api.previewTrialBalance(JSON.parse(settledKey)),
    enabled: settledKey !== '[]',
    placeholderData: (previous) => previous,
  });

  const save = useMutation({
    mutationFn: () =>
      api.submitTrialBalance(companyId, {
        reporting_period_id: Number(periodId),
        lines: payloadLines,
      }),
    onSuccess: onSaved,
  });

  const totalDebit = filled.reduce((sum, row) => sum + toAmount(row.debit), 0);
  const totalCredit = filled.reduce((sum, row) => sum + toAmount(row.credit), 0);
  const difference = Math.round((totalDebit - totalCredit) * 100) / 100;

  const update = (id, changes) =>
    setRows((current) =>
      current.map((row) =>
        row.id === id
          ? { ...row, ...changes, suggestion: 'category' in changes ? null : row.suggestion }
          : row,
      ),
    );

  // The file is read on the server, which finds the trial balance table in
  // a CSV or in any sheet of a workbook and suggests a category per account.
  async function importFile(file) {
    setImportMessage(null);
    setImportErrors([]);
    setImportWarnings([]);
    setImporting(true);
    try {
      const result = await api.importTrialBalance(companyId, file);
      setImported(result);
      const sheet = result.sheets.find((item) => item.name === result.selected_sheet);
      if (sheet) {
        applySheet(result, sheet);
      } else {
        setImportErrors([
          `No trial balance table was found in ${result.file_name}.`,
          ...result.sheets.flatMap((item) =>
            item.errors.map((error) =>
              result.file_type === 'xlsx' ? `${item.name}: ${error}` : error,
            ),
          ),
        ]);
      }
    } catch (error) {
      setImportErrors([error.message]);
    } finally {
      setImporting(false);
    }
  }

  function applySheet(result, sheet) {
    const lines = sheet.lines.map((line) =>
      newRow({
        account_code: line.account_code,
        account_name: line.account_name,
        account_group: line.account_group,
        source_ref: line.source_ref,
        debit: line.debit ? String(line.debit) : '',
        credit: line.credit ? String(line.credit) : '',
        category: line.category || '',
        suggestion: line.category ? line.basis : null,
      }),
    );
    setRows(lines.length ? lines : [newRow()]);
    setImportErrors(sheet.errors);
    setImportWarnings(sheet.warnings);
    const suggested = lines.filter((row) => row.suggestion).length;
    const missing = lines.filter((row) => !row.category).length;
    const where = result.file_type === 'xlsx' ? `sheet "${sheet.name}" of ${result.file_name}` : result.file_name;
    setImportMessage(
      [
        `Imported ${lines.length} accounts from ${where}`,
        sheet.skipped_rows.length
          ? ` (total or blank rows ${sheet.skipped_rows.join(', ')} skipped)`
          : '',
        '. ',
        suggested ? `${suggested} categories were filled in for you; check each one. ` : '',
        missing ? `${missing} accounts still need a category.` : '',
      ].join(''),
    );
  }

  const candidateSheets = imported?.sheets.filter((sheet) => sheet.header_row !== null) ?? [];

  const byStatement = (statement) =>
    (categories.data || []).filter((category) => category.statement === statement);

  const derived = payloadLines.length ? preview.data : undefined;
  const blocking = [
    ...unnamed.map(() => 'Every row with an amount needs an account name.').slice(0, 1),
    ...(derived?.errors || []),
  ];
  // Saving waits until the preview shown matches the rows as they are now.
  const canSave =
    payloadLines.length > 0 &&
    unnamed.length === 0 &&
    settledKey === payloadKey &&
    !preview.isFetching &&
    Boolean(derived?.is_valid);

  return (
    <form
      className="data-entry tb-entry"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSave) save.mutate();
      }}
    >
      <div>
        <section className="card reveal">
          <div className="tb-header">
            <div>
              <h2>Trial balance</h2>
              <p className="muted tb-intro">
                One row per account, as exported from the ledger (for example from Sage or
                Tally, as Excel or CSV). Each account is given a category, and the statement
                figures are calculated from them. Use the trial balance taken{' '}
                <strong>before closing entries</strong>.
              </p>
            </div>
            <div className="tb-actions">
              <input
                ref={fileInput}
                type="file"
                accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                hidden
                data-testid="tb-file"
                onChange={(event) => {
                  const [file] = event.target.files;
                  if (file) importFile(file);
                  event.target.value = '';
                }}
              />
              <button
                type="button"
                className="button button-small"
                onClick={() => fileInput.current?.click()}
                disabled={importing}
              >
                {importing ? 'Reading…' : 'Import Excel or CSV'}
              </button>
              <a className="button button-small button-quiet" href="/sample_trial_balance.csv" download>
                Sample file
              </a>
            </div>
          </div>

          {importMessage && <p className="alert alert-info">{importMessage}</p>}
          {candidateSheets.length > 1 && (
            <div className="field tb-sheet">
              <label htmlFor="tb-sheet">Sheet</label>
              <select
                id="tb-sheet"
                defaultValue={imported.selected_sheet}
                onChange={(event) =>
                  applySheet(imported, candidateSheets.find((s) => s.name === event.target.value))
                }
              >
                {candidateSheets.map((sheet) => (
                  <option key={sheet.name} value={sheet.name}>
                    {sheet.name} ({sheet.lines.length} accounts)
                  </option>
                ))}
              </select>
            </div>
          )}
          {importWarnings.length > 0 && (
            <div className="alert alert-warning">
              <ul className="alert-list">
                {importWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
          {importErrors.length > 0 && (
            <div className="alert alert-error">
              <ul className="alert-list">
                {importErrors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="table-scroll">
            <table className="data-table tb-table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Code</th>
                  <th scope="col">Account name</th>
                  <th scope="col" className="numeric">Debit</th>
                  <th scope="col" className="numeric">Credit</th>
                  <th scope="col">Category</th>
                  <th scope="col"><span className="visually-hidden">Remove</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={row.id}>
                    <td className="muted" title={row.source_ref || undefined}>
                      {index + 1}
                    </td>
                    <td>
                      <input
                        aria-label={`Row ${index + 1} account code`}
                        className="tb-code"
                        value={row.account_code}
                        onChange={(event) => update(row.id, { account_code: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`Row ${index + 1} account name`}
                        value={row.account_name}
                        onChange={(event) => update(row.id, { account_name: event.target.value })}
                      />
                      {(row.account_group || row.source_ref) && (
                        <span className="note">
                          {[row.account_group && `Group: ${row.account_group}`,
                            row.source_ref.split(' › ').slice(-2).join(' › ')]
                            .filter(Boolean)
                            .join(' · ')}
                        </span>
                      )}
                    </td>
                    {['debit', 'credit'].map((side) => (
                      <td key={side}>
                        <input
                          aria-label={`Row ${index + 1} ${side}`}
                          className="tb-amount"
                          type="number"
                          min="0"
                          step="0.01"
                          inputMode="decimal"
                          value={row[side]}
                          onChange={(event) => update(row.id, { [side]: event.target.value })}
                        />
                      </td>
                    ))}
                    <td>
                      <select
                        aria-label={`Row ${index + 1} category`}
                        className={row.category ? '' : 'tb-missing'}
                        value={row.category}
                        onChange={(event) => update(row.id, { category: event.target.value })}
                      >
                        <option value="">Choose…</option>
                        {[
                          ['income_statement', 'Income statement'],
                          ['balance_sheet', 'Balance sheet'],
                        ].map(([statement, title]) => (
                          <optgroup key={statement} label={title}>
                            {byStatement(statement).map((category) => (
                              <option key={category.code} value={category.code} title={category.examples}>
                                {category.label}
                              </option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                      {row.suggestion && (
                        <span className="note">{SUGGESTION_NOTES[row.suggestion]}</span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={`Remove row ${index + 1}`}
                        onClick={() => setRows((current) => current.filter((item) => item.id !== row.id))}
                      >
                        <Icon name="cross" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row" colSpan={3}>Total</th>
                  <td className="numeric">{formatMoney(totalDebit)}</td>
                  <td className="numeric">{formatMoney(totalCredit)}</td>
                  <td colSpan={2} className={difference === 0 ? 'identity-ok' : 'identity-bad'}>
                    <Icon name={difference === 0 ? 'check' : 'alert'} />
                    {difference === 0
                      ? 'Debits equal credits'
                      : `Out by ${formatMoney(Math.abs(difference))}`}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          <button
            type="button"
            className="button button-small button-quiet tb-add"
            onClick={() => setRows((current) => [...current, newRow()])}
          >
            <Icon name="plus" /> Add row
          </button>
        </section>
      </div>

      <aside className="data-entry-aside">
        <section className="card reveal" style={{ '--i': 1 }} aria-live="polite">
          <h2>Calculated statements</h2>
          {!derived && (
            <p className="muted tb-intro">
              The income statement and balance sheet figures appear here as you enter accounts.
              Open any figure to see which accounts make it up.
            </p>
          )}
          {blocking.length > 0 && (
            <div className="alert alert-error">
              <ul className="alert-list">
                {blocking.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </div>
          )}
          {derived?.warnings?.length > 0 && (
            <div className="alert alert-warning">
              <ul className="alert-list">
                {derived.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
          {derived?.inventory && (
            <InventoryPanel
              inventory={derived.inventory}
              currency={currency}
              onAdjust={(rows) => setRows((current) => [...current.filter((r) => !isBlank(r)), ...rows])}
            />
          )}
          {derived &&
            FIGURE_GROUPS.map((group) => (
              <div key={group.title} className="derived-group">
                <h3>{group.title}</h3>
                {group.figures.map(([key, label]) => (
                  <DerivedFigure
                    key={key}
                    label={label}
                    figure={derived.figures[key]}
                    currency={currency}
                  />
                ))}
              </div>
            ))}
        </section>

        {save.isError && <p className="alert alert-error">{save.error.message}</p>}
        <button type="submit" className="button" disabled={!canSave || save.isPending}>
          {save.isPending ? 'Saving…' : 'Save and assess'}
        </button>
      </aside>
    </form>
  );
}
