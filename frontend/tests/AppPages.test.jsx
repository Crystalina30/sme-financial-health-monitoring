import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import App from '../src/App.jsx';
import { ThemeProvider } from '../src/context/ThemeContext.jsx';
import { ClassificationPill } from '../src/components/StatusPill.jsx';
import { api } from '../src/services/apiClient.js';

// ECharts draws on a canvas, which jsdom does not provide; the charts are
// replaced with labelled placeholders so the page around them can be tested.
vi.mock('../src/charts/HealthScoreTrendChart.jsx', () => ({ default: () => <div>trend chart</div> }));
vi.mock('../src/charts/IndicatorStatusChart.jsx', () => ({ default: () => <div>status chart</div> }));
vi.mock('../src/charts/IndicatorTrendChart.jsx', () => ({ default: () => <div>indicator chart</div> }));

const COMPANY = { id: 1, name: 'CrystalCorps', industry: 'IT', currency_code: 'MYR' };

// The signed-in user; the real login flow is tested in AuthPage.test.jsx.
vi.mock('../src/context/AuthContext.jsx', () => ({
  useAuth: () => ({ user: { full_name: 'Crystalina Dibble', email: 'owner@example.com' }, isLoading: false, logout: () => {} }),
}));

// Reporting periods as the server holds them; the history tests change them.
const BASE_PERIODS = [
  { id: 1, company_id: 1, label: 'FY2024', period_start: '2024-01-01', period_end: '2024-12-31' },
  { id: 2, company_id: 1, label: 'FY2025', period_start: '2025-01-01', period_end: '2025-12-31' },
];
let periodsState = BASE_PERIODS;
const periodCalls = { update: async () => ({}), remove: async () => null };

// What GET /organisation returns; tests change it to cover setup.
const memberCalls = { add: async () => ({}), accept: async () => ({}) };
let invitationPreview = { organisation_name: 'CrystalCorps', role: 'clerk', email: 'owner@example.com', state: 'pending' };
let organisationState = { status: 'ready', organisation: COMPANY, candidates: [], role: 'admin' };

const category = (name, score, count) => ({
  category: name,
  score,
  applicable_indicator_count: count,
});

const OVERVIEW = {
  organisation: COMPANY,
  latest_period_id: 3,
  latest_assessed_period_id: 2,
  periods: [
    {
      id: 3, label: 'Q1 2026', period_start: '2026-01-01', period_end: '2026-03-31',
      period_days: 90, status: 'no_data', record: null, overall_score: null,
      classification: null, category_scores: [], scored_indicator_count: 0,
      total_indicator_count: 0, revenue: null, net_profit: null, data_quality_warnings: [],
    },
    {
      id: 2, label: 'FY2025', period_start: '2025-01-01', period_end: '2025-12-31',
      period_days: 365, status: 'assessed',
      record: { id: 9, revision: 2, source: 'statement', accounting_identity_ok: true, validation_notes: null },
      overall_score: 73.02, classification: 'sound',
      assessment_status: 'validated', is_provisional: false, reconciliation_difference: 0,
      category_scores: [
        category('liquidity', 81.5, 2), category('profitability', 60.25, 3),
        category('solvency', null, 0), category('efficiency', 77.3, 2),
      ],
      scored_indicator_count: 7, total_indicator_count: 10,
      revenue: 1250000, net_profit: -80000,
      data_quality_warnings: ['Only 7 of 10 indicators could be scored.'],
    },
    {
      id: 1, label: 'FY2024', period_start: '2024-01-01', period_end: '2024-12-31',
      period_days: 366, status: 'assessed',
      record: { id: 8, revision: 1, source: 'trial_balance', accounting_identity_ok: true, validation_notes: null },
      overall_score: 47.25, classification: 'vulnerable',
      assessment_status: 'provisional', is_provisional: true, reconciliation_difference: 1198800,
      category_scores: [], scored_indicator_count: 10, total_indicator_count: 10,
      revenue: 1200, net_profit: 100000, data_quality_warnings: [],
    },
  ],
};

const indicator = (code, display_name, category, status, score) => ({
  code,
  display_name,
  category,
  unit: 'times',
  value: 1.2,
  score,
  status,
  is_applicable: status !== 'not_applicable',
  note: null,
  threshold: {
    direction: 'higher_is_better',
    concern_threshold: 1.5,
    distress_threshold: 1,
    floor_value: 0,
    target_value: 2,
    source_reference: 'Test source',
    basis: 'Test basis',
    description: '',
  },
  change: null,
  effective_weight: score === null ? null : 0.25,
});

const DASHBOARD = {
  assessment: {
    company_id: 1,
    reporting_period_id: 2,
    period_label: 'FY2025',
    period_days: 365,
    methodology_version: '2.0',
    overall_score: 54.3,
    classification: 'vulnerable',
    scored_indicator_count: 1,
    total_indicator_count: 2,
    category_scores: [
      { category: 'liquidity', score: 48.2, applicable_indicator_count: 2 },
      { category: 'profitability', score: 61, applicable_indicator_count: 3 },
      { category: 'solvency', score: null, applicable_indicator_count: 0 },
      { category: 'efficiency', score: 70.5, applicable_indicator_count: 1 },
    ],
    indicators: [
      indicator('current_ratio', 'Current ratio', 'liquidity', 'concern', 48),
      indicator('debt_ratio', 'Debt ratio', 'solvency', 'not_applicable', null),
    ],
    attention: [
      { code: 'current_ratio', display_name: 'Current ratio', priority: 1, reason: 'concern_breach', status: 'concern' },
      { code: 'debt_ratio', display_name: 'Debt ratio', priority: 2, reason: null, status: 'not_applicable' },
    ],
    robustness: {
      arithmetic_score: 54.3,
      geometric_score: 0,
      difference: 54.3,
      arithmetic_classification: 'vulnerable',
      geometric_classification: 'distressed',
      classifications_differ: true,
      has_zero_category: true,
      weakest_category: 'liquidity',
      weakest_category_score: 48.2,
    },
    benchmark: {
      model: "Altman Z''",
      source: 'Altman (2002)',
      available: false,
      value: null,
      components: {},
      coefficients: { x1: 6.56, x2: 3.26, x3: 6.72, x4: 1.05 },
      distress_cutoff: 1.1,
      below_distress_cutoff: null,
      missing_inputs: ['retained_earnings'],
      reason: 'Retained earnings have not been entered for this period.',
    },
    data_quality_notes: ['1 of 2 indicators could be scored.'],
    accounting_identity_ok: true,
    validation_notes: null,
    assessment_status: 'provisional',
    is_provisional: true,
    data_quality_issues: [
      {
        severity: 'material',
        code: 'net_profit_unreconciled',
        message: 'Reported net profit (100,000.00) differs from the calculated net profit (-1,098,800.00) by 1,198,800.00.',
      },
      { severity: 'info', code: 'data_quality_note', message: '1 of 2 indicators could be scored.' },
    ],
    income_statement_reconciliation: {
      revenue: 1200, cost_of_goods_sold: 780000, gross_profit: -778800,
      other_operating_income: 0, operating_expenses: 260000, operating_profit: -1038800,
      other_income: 0, other_expenses: 0, interest_expense: 30000, profit_before_tax: -1068800,
      tax_expense: 30000, calculated_net_profit: -1098800, reported_net_profit: 100000,
      difference: 1198800, tolerance: 0.01, reconciled: false,
    },
    reported_net_profit: 100000,
    calculated_net_profit: -1098800,
    reconciliation_difference: 1198800,
    checks_performed: [
      { name: 'Balance sheet balances (assets = liabilities + equity)', passed: true, detail: 'Exact decimal check; tolerance 0.01 for exact figures (to the sen).' },
      { name: 'Net profit reconciles with the income statement lines', passed: false, detail: 'Difference 1,198,800.00; tolerance 0.01 for exact figures (to the sen).' },
      { name: 'Trial balance checks', passed: null, detail: 'Not applicable: the figures were entered as statement totals, so account-level completeness could not be checked.' },
    ],
    presentation_unit: 0.01,
  },
  financial_summary: {
    revenue: 1350000,
    gross_profit: 450000,
    operating_profit: 150000,
    net_profit: -80000,
    total_assets: 1250000,
    total_liabilities: 760000,
    total_equity: 490000,
    cost_of_goods_sold: 900000,
    operating_expenses: 300000,
    interest_expense: 45000,
    accounts_receivable: 240000,
    inventory: null,
    current_assets: 540000,
    current_liabilities: 420000,
    retained_earnings: null,
  },
  score_trend: [
    { reporting_period_id: 1, period_label: 'FY2024', period_end: '2024-12-31', overall_score: 63, classification: 'sound' },
    { reporting_period_id: 2, period_label: 'FY2025', period_end: '2025-12-31', overall_score: 54.3, classification: 'vulnerable' },
  ],
};

vi.mock('../src/services/apiClient.js', () => ({
  api: {
    getOrganisation: async () => organisationState,
    getOverview: async () => OVERVIEW,
    listMembers: async () => [
      { id: 1, email: 'owner@example.com', full_name: 'Crystalina Dibble', role: 'admin', status: 'active', is_you: true, is_owner: true },
      { id: 2, email: 'clerk@example.com', full_name: 'Finance Clerk', role: 'clerk', status: 'active', is_you: false, is_owner: false },
    ],
    listInvitations: async () => [
      { id: 7, email: 'new@example.com', role: 'clerk', state: 'pending', created_at: '2026-11-25T10:00:00Z', expires_at: '2026-12-02T10:00:00Z' },
      { id: 6, email: 'old@example.com', role: 'clerk', state: 'expired', created_at: '2026-11-01T10:00:00Z', expires_at: '2026-11-08T10:00:00Z' },
    ],
    createInvitation: (...args) => memberCalls.add(...args),
    revokeInvitation: async () => null,
    getAuditLog: async () => [
      { id: 2, created_at: '2026-11-25T10:05:00Z', actor_email: 'clerk@example.com', action: 'record.corrected', entity_type: 'financial_record', entity_id: 9, detail: { period: 'FY2025', from_revision: 1, to_revision: 2, changed: { revenue: { from: 1, to: 2 } } } },
      { id: 1, created_at: '2026-11-25T10:00:00Z', actor_email: 'owner@example.com', action: 'invitation.created', entity_type: 'invitation', entity_id: 7, detail: { email: 'new@example.com', role: 'clerk' } },
    ],
    previewInvitation: async () => invitationPreview,
    acceptInvitation: (...args) => memberCalls.accept(...args),
    updateMember: async () => ({}),
    removeMember: async () => null,
    updateCompany: async () => COMPANY,
    setUpOrganisation: async (data) => {
      organisationState = { status: 'ready', organisation: { ...COMPANY, ...data, id: 5 }, candidates: [], role: 'admin' };
      return organisationState.organisation;
    },
    getCompany: async () => COMPANY,
    listPeriods: async () => periodsState,
    updatePeriod: (...args) => periodCalls.update(...args),
    deletePeriod: (...args) => periodCalls.remove(...args),
    createPeriod: async () => ({}),
    listRecords: async () => [{ id: 9, reporting_period_id: 1, revision: 1, is_current: true }],
    getDashboard: async () => DASHBOARD,
    listAccountCategories: async () => ACCOUNT_CATEGORIES,
    suggestCategories: async (_companyId, lines) => ({
      suggestions: lines.map((line) =>
        /bank/i.test(line.account_name)
          ? { category: 'cash', basis: 'account_name' }
          : { category: null, basis: null },
      ),
    }),
    previewTrialBalance: async (lines) => previewFor(lines),
    importTrialBalance: async (_companyId, file) => importResultFor(file.name),
  },
}));

const ACCOUNT_CATEGORIES = [
  { code: 'revenue', label: 'Revenue', statement: 'income_statement', normal_side: 'credit', examples: 'Sales' },
  { code: 'cash', label: 'Cash and bank', statement: 'balance_sheet', normal_side: 'debit', examples: 'Bank' },
  { code: 'equity', label: 'Share capital and reserves', statement: 'balance_sheet', normal_side: 'credit', examples: 'Capital' },
];

// A stand-in for the server's file reader: a workbook with two tables.
function importResultFor(fileName) {
  const line = (name, group, debit, credit, category, basis, row) => ({
    account_code: '', account_name: name, account_group: group, debit, credit, category,
    basis, source_ref: `${fileName} › Trial Balance › row ${row}`,
  });
  return {
    file_name: fileName,
    file_type: 'xlsx',
    selected_sheet: 'Trial Balance',
    sheets: [
      { name: 'Inputs', header_row: null, columns: {}, lines: [], skipped_rows: [],
        total_debit: 0, total_credit: 0, errors: ['No header row'], warnings: [] },
      {
        name: 'Trial Balance', header_row: 1, columns: {}, skipped_rows: [4],
        total_debit: 5000, total_credit: 5000, errors: [], warnings: [],
        lines: [
          line('Maybank current account', 'Bank Accounts', 5000, 0, 'cash', 'account_group', 2),
          line('Share capital', '', 0, 5000, null, null, 3),
        ],
      },
      {
        name: 'Old TB', header_row: 1, columns: {}, skipped_rows: [],
        total_debit: 10, total_credit: 10, errors: [], warnings: [],
        lines: [line('Petty cash', '', 10, 0, 'cash', 'account_name', 2)],
      },
    ],
  };
}

// A stand-in for the server's calculation: enough to show the figures panel.
function previewFor(lines) {
  const figure = (value, contributions = []) => ({ value, formula: 'Σ accounts', contributions });
  const cash = lines.filter((line) => line.category === 'cash');
  const debit = lines.reduce((sum, line) => sum + line.debit, 0);
  const credit = lines.reduce((sum, line) => sum + line.credit, 0);
  const uncategorised = lines.filter((line) => !line.category);
  const errors = [
    ...(debit === credit ? [] : ['The trial balance does not balance.']),
    ...uncategorised.map((line) => `${line.account_name} has no category.`),
  ];
  const cashTotal = cash.reduce((sum, line) => sum + line.debit - line.credit, 0);
  const names = ['revenue', 'cost_of_goods_sold', 'operating_expenses', 'interest_expense',
    'tax_expense', 'net_profit', 'accounts_receivable', 'inventory', 'current_assets',
    'total_assets', 'current_liabilities', 'total_liabilities', 'total_equity', 'retained_earnings'];
  return {
    figures: {
      ...Object.fromEntries(names.map((name) => [name, figure(0)])),
      cash_and_equivalents: figure(
        cashTotal,
        cash.map((line, index) => ({
          line_number: index + 1, account_code: line.account_code,
          account_name: line.account_name, category: 'cash', amount: line.debit - line.credit,
        })),
      ),
    },
    category_totals: {},
    total_debit: debit,
    total_credit: credit,
    difference: debit - credit,
    is_valid: errors.length === 0,
    errors,
    warnings: [],
  };
}

function CurrentPath() {
  return <p data-testid="path">{useLocation().pathname + useLocation().search}</p>;
}

function renderAt(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <App />
          <CurrentPath />
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

const breadcrumb = () => screen.getByRole('navigation', { name: 'Breadcrumb' });

describe('financial overview', () => {
  it('opens on the overview with no company selector', async () => {
    renderAt('/');
    expect(await screen.findByRole('heading', { level: 1, name: 'CrystalCorps' })).toBeInTheDocument();
    expect(screen.getByTestId('path')).toHaveTextContent('/overview');
    expect(breadcrumb()).toHaveTextContent('Financial Overview');
    expect(breadcrumb()).not.toHaveTextContent('Companies');
    expect(screen.queryByText('Your companies')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /New company/ })).not.toBeInTheDocument();
    const tags = screen.getByRole('list', { name: 'Organisation details' });
    expect(tags).toHaveTextContent('IT');
    expect(tags).toHaveTextContent('MYR');
    // The latest period is chosen by date, and shown with its exact dates.
    expect(tags).toHaveTextContent('Latest period: Q1 2026 (1 Jan 2026 – 31 Mar 2026)');
  });

  it('shows the latest assessed figures from the server, not placeholders', async () => {
    renderAt('/overview');
    await screen.findByRole('heading', { level: 1, name: 'CrystalCorps' });
    expect(screen.getByText(/Q1 2026 has no financial data yet, so the figures below are from FY2025/))
      .toBeInTheDocument();
    const summary = document.querySelector('.overview-summary');
    // The ring counts up to the score.
    await waitFor(() => expect(summary).toHaveTextContent('73.0'), { timeout: 3000 });
    expect(summary).toHaveTextContent('based on 7 of 10 indicators');
    expect(within(summary).getByText('Total revenue').closest('.stat-tile')).toHaveTextContent('1,250,000');
    expect(within(summary).getByText('Net profit').closest('.stat-tile')).toHaveTextContent('-80,000');
    // Incomplete data is flagged, not hidden.
    // FY2025 is validated, so its notes are informational, not a warning.
    expect(screen.getByText(/Notes on the data for FY2025/)).toBeInTheDocument();
    expect(screen.getByText('Only 7 of 10 indicators could be scored.')).toBeInTheDocument();
  });

  it('shows the four category scores from the engine, N/A when not scored', async () => {
    renderAt('/overview');
    const meter = await screen.findByRole('meter', { name: 'Liquidity score' });
    expect(meter).toHaveAttribute('aria-valuenow', '81.5');
    expect(screen.getByRole('meter', { name: 'Solvency score' })).toHaveAttribute(
      'aria-valuetext', 'Not applicable',
    );
    expect(screen.getByText('No indicator could be scored')).toBeInTheDocument();
  });

  it('lists recent periods without inventing scores', async () => {
    renderAt('/overview');
    const table = (await screen.findByRole('heading', { name: 'Financial history' }))
      .closest('section').querySelector('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => row.querySelector('th').textContent)).toEqual(['Q1 2026', 'FY2025', 'FY2024']);
    expect(rows[0]).toHaveTextContent('N/A');
    expect(rows[0]).toHaveTextContent('No financial data');
    expect(rows[0]).toHaveTextContent('90 days');
    expect(rows[1]).toHaveTextContent('Data: Checks passed');
    expect(rows[2]).toHaveTextContent('Vulnerable');
    // A leap year is a normal year: no length note.
    expect(rows[2]).not.toHaveTextContent('366 days');
  });

  it('quick actions lead to the existing pages', async () => {
    renderAt('/overview');
    await screen.findByRole('heading', { name: 'Quick actions' });
    const link = (name) => screen.getByRole('link', { name: new RegExp(name) });
    expect(link('Import trial balance')).toHaveAttribute('href', '/periods/3/data?mode=trial_balance');
    expect(link('Enter statement totals')).toHaveAttribute('href', '/periods/3/data?mode=statement');
    expect(link('View financial analysis')).toHaveAttribute('href', '/periods/2/dashboard');
    expect(link('View financial history')).toHaveAttribute('href', '/history');
    expect(link('Manage reporting periods')).toHaveAttribute('href', '/history');
  });

  it('has single-organisation navigation and the organisation name', async () => {
    renderAt('/overview');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual([
      'Financial Overview', 'Financial Data', 'Financial Analysis', 'Financial History', 'Company Settings',
    ]);
    expect(within(nav).getByRole('link', { name: 'Financial Overview' })).toHaveAttribute('aria-current', 'page');
    expect(document.querySelector('.org-chip')).toHaveTextContent('CrystalCorps');
  });

  it('Financial Analysis opens the latest assessed period', async () => {
    renderAt('/analysis');
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/periods/2/dashboard'));
  });

  it('old /companies addresses lead to the new pages', async () => {
    renderAt('/periods/2/data');
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/periods/2/data'));
  });
});

describe('organisation setup', () => {
  it('sends an account without an organisation to the one-time setup', async () => {
    organisationState = { status: 'setup_required', organisation: null, candidates: [] };
    try {
      renderAt('/overview');
      expect(await screen.findByRole('heading', { name: 'Set up your organisation' })).toBeInTheDocument();
      expect(screen.getByTestId('path')).toHaveTextContent('/setup');
      // No navigation until there is an organisation.
      expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument();

      fireEvent.change(screen.getByLabelText('Organisation name'), { target: { value: 'New Sdn Bhd' } });
      fireEvent.click(screen.getByRole('button', { name: /Save and continue/ }));
      await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/overview'));
    } finally {
      organisationState = { status: 'ready', organisation: COMPANY, candidates: [], role: 'admin' };
    }
  });

  it('asks an account with several old companies to choose one', async () => {
    organisationState = {
      status: 'selection_required',
      organisation: null,
      candidates: [{ ...COMPANY, id: 1 }, { ...COMPANY, id: 2, name: 'Second Co' }],
    };
    try {
      renderAt('/overview');
      expect(await screen.findByRole('heading', { name: 'Choose your organisation' })).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: /Second Co/ })).toBeInTheDocument();
      expect(screen.getByText(/the others are kept unchanged and are not deleted/)).toBeInTheDocument();
    } finally {
      organisationState = { status: 'ready', organisation: COMPANY, candidates: [], role: 'admin' };
    }
  });

  it('an account with an organisation cannot open setup again', async () => {
    renderAt('/setup');
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/overview'));
  });
});

describe('financial history (reporting periods)', () => {
  it('shows each period with its data status and the right actions', async () => {
    renderAt('/history');
    expect(await screen.findByText('FY2024')).toBeInTheDocument();
    expect(screen.getByText('Entered (revision 1)')).toBeInTheDocument();
    expect(screen.getByText('Not entered')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Dashboard' })).toHaveLength(1);
    expect(breadcrumb()).toHaveTextContent('Financial Overview');
    expect(breadcrumb()).toHaveTextContent('Financial History');
    expect(screen.getAllByRole('link', { name: 'Dashboard' })[0]).toHaveAttribute('href', '/periods/1/dashboard');
    // Dates are readable and the period length is shown.
    expect(screen.getByText('1 Jan 2024 – 31 Dec 2024 · 366 days')).toBeInTheDocument();
  });

  it('shows the dates and length of a short period without a warning', async () => {
    periodsState = [{ ...BASE_PERIODS[1], period_end: '2025-01-31' }];
    try {
      renderAt('/history');
      expect(await screen.findByText('1 Jan 2025 – 31 Jan 2025 · 31 days')).toBeInTheDocument();
      expect(screen.queryByText(/Not a full year/i)).not.toBeInTheDocument();
    } finally {
      periodsState = BASE_PERIODS;
    }
  });

  it('corrects a period\'s dates', async () => {
    periodsState = [{ ...BASE_PERIODS[1], period_end: '2025-01-31' }];
    const update = vi.fn(async () => ({}));
    periodCalls.update = update;
    try {
      renderAt('/history');
      fireEvent.click(await screen.findByRole('button', { name: 'Edit period FY2025' }));
      const form = screen.getByRole('form', { name: 'Edit FY2025' });
      fireEvent.change(within(form).getByLabelText('End'), { target: { value: '2025-12-31' } });
      expect(form).toHaveTextContent('365 days');
      fireEvent.click(within(form).getByRole('button', { name: /Save period/ }));
      await waitFor(() => expect(update).toHaveBeenCalledWith('1', 2, {
        label: 'FY2025', period_start: '2025-01-01', period_end: '2025-12-31',
      }));
    } finally {
      periodsState = BASE_PERIODS;
      periodCalls.update = async () => ({});
    }
  });

  it('asks for confirmation before deleting, and cancelling deletes nothing', async () => {
    const remove = vi.fn(async () => null);
    periodCalls.remove = remove;
    try {
      renderAt('/history');
      fireEvent.click(await screen.findByRole('button', { name: 'Delete period FY2024' }));
      const dialog = screen.getByRole('alertdialog', { name: 'Delete FY2024?' });
      expect(dialog).toHaveTextContent('its financial data and every earlier revision');
      expect(dialog).toHaveTextContent('This cannot be undone.');
      // The safe choice has focus.
      expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus();

      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
      expect(remove).not.toHaveBeenCalled();

      fireEvent.click(screen.getByRole('button', { name: 'Delete period FY2024' }));
      fireEvent.keyDown(screen.getByRole('alertdialog'), { key: 'Escape' });
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
      expect(remove).not.toHaveBeenCalled();

      fireEvent.click(screen.getByRole('button', { name: 'Delete period FY2024' }));
      fireEvent.click(screen.getByRole('button', { name: 'Delete period' }));
      // The period is named in the request, so a wrong id cannot delete it.
      await waitFor(() => expect(remove).toHaveBeenCalledWith('1', 1, 'FY2024'));
      await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    } finally {
      periodCalls.remove = async () => null;
    }
  });

  it('fills in a one-year end date when a start date is chosen', async () => {
    renderAt('/history');
    const start = await screen.findByLabelText('Start');
    fireEvent.change(start, { target: { value: '2026-04-01' } });
    expect(screen.getByLabelText('End')).toHaveValue('2027-03-31');
    expect(screen.getByText(/1 Apr 2026 – 31 Mar 2027 · 365 days/)).toBeInTheDocument();
    // Once the user sets the end, it is theirs.
    fireEvent.change(screen.getByLabelText('End'), { target: { value: '2026-06-30' } });
    fireEvent.change(start, { target: { value: '2026-05-01' } });
    expect(screen.getByLabelText('End')).toHaveValue('2026-06-30');
    expect(screen.getByText(/1 May 2026 – 30 Jun 2026 · 61 days/)).toBeInTheDocument();
  });
});

describe('dashboard', () => {
  it('renders the score, categories, summary and attention list', async () => {
    renderAt('/periods/2/dashboard');
    expect(await screen.findByRole('heading', { name: 'Financial health' })).toBeInTheDocument();

    // The classification is named in words, not shown by colour alone.
    expect(document.querySelector('.score-band')).toHaveTextContent('Vulnerable');
    // A category with no applicable indicators reads N/A, never zero.
    const solvency = within(document.querySelector('.category-grid')).getAllByText('Solvency')[0];
    expect(solvency.closest('.category-card').querySelector('.flip-front')).toHaveTextContent('N/A');
    expect(screen.getByText('0 indicators applicable')).toBeInTheDocument();
    expect(screen.getByText(/based on 1 of 2 indicators/)).toBeInTheDocument();

    const summary = within(document.querySelector('.stat-grid'));
    expect(summary.getByText('Net profit').closest('.stat-tile')).toHaveTextContent('-80,000');
    expect(screen.getByText('Concern threshold breached')).toBeInTheDocument();
    expect(screen.getByText('trend chart')).toBeInTheDocument();
    expect(breadcrumb()).toHaveTextContent('Financial Overview');
    expect(breadcrumb()).toHaveTextContent('FY2025');
    expect(breadcrumb()).toHaveTextContent('Financial Analysis');
  });

  it('flags the weakest category and explains data-quality limits', async () => {
    renderAt('/periods/2/dashboard');
    await screen.findByRole('heading', { name: 'Financial health' });

    const liquidity = within(document.querySelector('.category-grid')).getAllByText('Liquidity')[0];
    expect(liquidity.closest('.category-card')).toHaveClass('is-weakest');
    expect(screen.getByText('Weakest')).toBeInTheDocument();
    expect(screen.getByText('1 of 2 indicators could be scored.')).toBeInTheDocument();
  });

  it('does not display the robustness check or the distress benchmark', async () => {
    renderAt('/periods/2/dashboard');
    await screen.findByRole('heading', { name: 'Financial health' });
    expect(screen.queryByRole('heading', { name: 'Robustness check' })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: /Financial Distress Benchmark/ }),
    ).not.toBeInTheDocument();
  });

  it('turns a category card over to show how its score is averaged', async () => {
    renderAt('/periods/2/dashboard');
    await screen.findByRole('heading', { name: 'Financial health' });

    const card = within(document.querySelector('.category-grid'))
      .getAllByText('Liquidity')[0]
      .closest('.flip-card');
    const back = card.querySelector('.flip-back');
    expect(card).not.toHaveClass('is-flipped');
    expect(back).toHaveAttribute('aria-hidden', 'true');

    fireEvent.click(card.querySelector('.flip-front'));

    expect(card).toHaveClass('is-flipped');
    expect(back).toHaveAttribute('aria-hidden', 'false');
    expect(back).toHaveTextContent('(48.00) ÷ 1 = 48.2');
    // Focus follows to the face now showing.
    expect(screen.getByRole('button', { name: 'Back to Liquidity' })).toHaveFocus();

    fireEvent.click(screen.getByRole('button', { name: 'Back to Liquidity' }));
    expect(card).not.toHaveClass('is-flipped');
  });

  it('turns an indicator card over to show formula, thresholds and weight', async () => {
    renderAt('/periods/2/dashboard');
    await screen.findByRole('heading', { name: 'Financial health' });

    fireEvent.click(screen.getByRole('button', { name: 'Show how Current ratio is calculated' }));

    const card = screen.getByRole('button', { name: 'Back to Current ratio' }).closest('.flip-card');
    const back = card.querySelector('.flip-back');
    expect(card).toHaveClass('is-flipped');
    expect(back).toHaveTextContent('Current assets ÷ Current liabilities');
    for (const name of ['Floor', 'Distress', 'Concern', 'Target', 'Value', 'Score', 'Weight']) {
      expect(back).toHaveTextContent(name);
    }
    expect(back).toHaveTextContent('25.0%');
    // The threshold basis is kept, in the formula's tooltip.
    expect(back.querySelector('.indicator-back-formula').title).toContain('Test basis');
  });

  it('turns the overall score card over to show the bands', async () => {
    renderAt('/periods/2/dashboard');
    await screen.findByRole('heading', { name: 'Financial health' });

    fireEvent.click(screen.getByRole('button', { name: 'Show how the overall score is calculated' }));
    const back = document.querySelector('.overall-card .flip-back');
    expect(back).toHaveTextContent('Insufficient data');
    expect(back).toHaveTextContent('Methodology 2.0');
  });

  it('no longer has the long explanation section', async () => {
    renderAt('/periods/2/dashboard');
    await screen.findByRole('heading', { name: 'Financial health' });
    expect(screen.queryByText('How this score is calculated')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'All indicators' })).not.toBeInTheDocument();
  });
});

describe('insufficient data', () => {
  it('is labelled as a data problem, not as distress', () => {
    render(<ClassificationPill classification="insufficient_data" />);
    expect(screen.getByText('Insufficient data')).toHaveClass('pill-not_applicable');
  });
});

describe('financial data entry', () => {
  it('checks the accounting identity to the cent and shows the exact gap', async () => {
    renderAt('/periods/2/data?mode=statement');
    const assets = await screen.findByLabelText('Total assets');
    fireEvent.change(assets, { target: { value: '110000' } });
    fireEvent.change(screen.getByLabelText('Total liabilities'), { target: { value: '60000' } });
    const equity = screen.getByLabelText('Total equity');
    const panel = () => screen.getByRole('heading', { name: 'Accounting identity' }).closest('section');

    // RM1,000 on RM110,000 is under 1% but is still an error.
    fireEvent.change(equity, { target: { value: '49000' } });
    expect(panel()).toHaveTextContent('Out by MYR 1,000.00: total assets are higher');
    expect(panel()).toHaveTextContent('MYR 109,000.00');

    fireEvent.change(equity, { target: { value: '49999.99' } });
    expect(panel()).toHaveTextContent('The identity holds.');

    fireEvent.change(equity, { target: { value: '49999.98' } });
    expect(panel()).toHaveTextContent('Out by MYR 0.02');

    // Negative equity is fine when the equation balances.
    fireEvent.change(screen.getByLabelText('Total liabilities'), { target: { value: '130000' } });
    fireEvent.change(equity, { target: { value: '-20000' } });
    expect(panel()).toHaveTextContent('The identity holds.');
  });

  it('starts a new period with the trial balance and can switch to statement totals', async () => {
    renderAt('/periods/2/data');
    expect(await screen.findByRole('heading', { name: 'Trial balance' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Trial balance' })).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(screen.getByRole('button', { name: 'Statement totals' }));
    expect(screen.getByLabelText('Cost of goods sold')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Trial balance' })).not.toBeInTheDocument();
  });

  it('imports a workbook, suggests categories and shows where each figure comes from', async () => {
    renderAt('/periods/2/data');
    await screen.findByRole('heading', { name: 'Trial balance' });
    await screen.findAllByRole('option', { name: 'Cash and bank' });

    const file = new File(['xlsx bytes'], 'tb.xlsx');
    fireEvent.change(screen.getByTestId('tb-file'), { target: { files: [file] } });

    expect(await screen.findByDisplayValue('Maybank current account')).toBeInTheDocument();
    expect(
      screen.getByText(/Imported 2 accounts from sheet "Trial Balance" of tb.xlsx/),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Row 1 category')).toHaveValue('cash');
    expect(screen.getByText('from its group')).toBeInTheDocument();
    // The group and source row are kept and shown with the account.
    expect(screen.getByText(/Group: Bank Accounts · Trial Balance › row 2/)).toBeInTheDocument();
    // Only sheets that hold a trial balance table can be chosen.
    expect(screen.getByLabelText('Sheet')).toHaveValue('Trial Balance');
    expect(screen.getAllByRole('option', { name: /accounts\)$/ })).toHaveLength(2);
    // The account the rules do not recognise is left for the user to choose.
    expect(screen.getByLabelText('Row 2 category')).toHaveValue('');
    expect(screen.getByText('Debits equal credits')).toBeInTheDocument();

    // Saving waits until every account has a category.
    expect(await screen.findByText('Share capital has no category.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save and assess' })).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Row 2 category'), { target: { value: 'equity' } });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Save and assess' })).toBeEnabled(),
    );

    const cash = screen.getByText('Cash and equivalents').closest('details');
    expect(cash).toHaveTextContent('5,000');
    expect(cash).toHaveTextContent('Maybank current account');

    // Choosing another sheet replaces the rows.
    fireEvent.change(screen.getByLabelText('Sheet'), { target: { value: 'Old TB' } });
    expect(await screen.findByDisplayValue('Petty cash')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('Maybank current account')).not.toBeInTheDocument();
  });
});

describe('dashboard figures from a trial balance', () => {
  it('opens a figure to show the accounts and source rows behind it', async () => {
    const original = { listRecords: api.listRecords, getTrialBalance: api.getTrialBalance };
    api.listRecords = async () => [
      { id: 12, reporting_period_id: 2, revision: 1, is_current: true, source: 'trial_balance' },
    ];
    const contribution = (name, amount, row) => ({
      line_number: row, account_code: '', account_name: name, category: 'cost_of_sales',
      amount, source_ref: `tb.xlsx › Trial Balance › row ${row}`,
    });
    api.getTrialBalance = async () => ({
      financial_record_id: 12,
      revision: 1,
      lines: [],
      derivation: {
        figures: {
          cost_of_goods_sold: {
            value: 900000,
            formula: 'Σ Cost of sales accounts (debit − credit)',
            contributions: [contribution('Purchases', 950000, 13), contribution('Closing stock', -50000, 14)],
          },
        },
      },
    });
    try {
      renderAt('/periods/2/dashboard');
      const button = await screen.findByRole('button', { name: 'Cost of goods sold' });
      // Figures without a trace stay plain text.
      expect(screen.queryByRole('button', { name: 'Revenue' })).not.toBeInTheDocument();

      fireEvent.click(button);
      const trace = screen.getByRole('region', { name: 'How Cost of goods sold is calculated' });
      expect(trace).toHaveTextContent('Σ Cost of sales accounts');
      expect(trace).toHaveTextContent('Purchases');
      expect(trace).toHaveTextContent('tb.xlsx › Trial Balance › row 14');
      expect(trace).toHaveTextContent('−50,000');
      expect(button).toHaveAttribute('aria-expanded', 'true');
    } finally {
      Object.assign(api, original);
    }
  });
});

describe('assessment reliability', () => {
  it('shows a provisional assessment with the reconciliation figures, apart from health', async () => {
    renderAt('/periods/2/dashboard');
    const banner = await screen.findByRole('alert');
    expect(within(banner).getByRole('heading', {
      name: 'Provisional Assessment — Financial data requires review',
    })).toBeInTheDocument();
    expect(banner).toHaveTextContent('1,198,800.00');
    expect(banner).toHaveTextContent('Reported net profit');
    expect(banner).toHaveTextContent('MYR 100,000.00');
    expect(banner).toHaveTextContent('MYR -1,098,800.00');
    expect(within(banner).getByRole('link', { name: /Review financial data/ }))
      .toHaveAttribute('href', '/periods/2/data');
    // Health classification and data reliability are separate badges.
    const front = document.querySelector('.overall-card .flip-front');
    expect(front.querySelector('.score-band')).toHaveTextContent('Vulnerable');
    expect(front.querySelector('.reliability-badge')).toHaveTextContent('Data: Provisional');
  });

  it('a validated assessment carries a badge and no banner', async () => {
    const original = api.getDashboard;
    api.getDashboard = async () => ({
      ...DASHBOARD,
      assessment: {
        ...DASHBOARD.assessment,
        assessment_status: 'validated',
        is_provisional: false,
        data_quality_issues: [],
        income_statement_reconciliation: { ...DASHBOARD.assessment.income_statement_reconciliation, reconciled: true, difference: 0 },
      },
    });
    try {
      renderAt('/periods/2/dashboard');
      await screen.findByRole('heading', { name: 'Financial health' });
      expect(screen.queryByText(/Provisional Assessment/)).not.toBeInTheDocument();
      expect(document.querySelector('.reliability-badge')).toHaveTextContent('Data: Checks passed');
    } finally {
      api.getDashboard = original;
    }
  });

  it('says plainly when financial health cannot be assessed', async () => {
    const original = api.getDashboard;
    api.getDashboard = async () => ({
      ...DASHBOARD,
      assessment: {
        ...DASHBOARD.assessment,
        overall_score: null,
        classification: 'insufficient_data',
        assessment_status: 'insufficient_data',
        is_provisional: false,
        data_quality_issues: [{
          severity: 'material', code: 'insufficient_data',
          message: 'Essential financial information is unavailable (total assets).',
        }],
      },
    });
    try {
      renderAt('/periods/2/dashboard');
      const banner = await screen.findByRole('alert');
      expect(banner).toHaveTextContent('Insufficient Data — Financial health cannot be assessed');
      expect(banner).toHaveTextContent('Essential financial information is unavailable');
      expect(document.querySelector('.overall-card .flip-front')).toHaveTextContent('N/A');
    } finally {
      api.getDashboard = original;
    }
  });

  it('the overview shows each period\u2019s reliability', async () => {
    renderAt('/overview');
    const table = (await screen.findByRole('heading', { name: 'Financial history' }))
      .closest('section').querySelector('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows[1]).toHaveTextContent('Data: Checks passed');
    expect(rows[2]).toHaveTextContent('Data: Provisional');
  });

  it('reconciles net profit live on the statement form', async () => {
    renderAt('/periods/2/data?mode=statement');
    const set = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
    await screen.findByLabelText('Revenue');
    set('Revenue', '1200');
    set('Cost of goods sold', '780000');
    set('Operating expenses', '260000');
    set('Interest expense (finance costs)', '30000');
    set('Tax expense (negative for a tax credit)', '30000');
    set('Net profit (as reported)', '100000');
    const panel = screen.getByRole('heading', { name: 'Net profit reconciliation' }).closest('section');
    expect(panel).toHaveTextContent('Calculated net profitMYR -1,098,800.00');
    expect(panel).toHaveTextContent('differs from the calculated figure by MYR 1,198,800.00');
    expect(panel).toHaveTextContent('the assessment will be Provisional');

    // A legitimate line explains the gap: the statement then reconciles.
    set('Revenue', '1200000');
    set('Net profit (as reported)', '110000');
    set('Other non-operating income (optional, e.g. interest received, gains)', '10000');
    expect(panel).toHaveTextContent('Net profit reconciles with its lines.');
  });
});

describe('what the checks mean, rounding and stock', () => {
  it('lists what was checked and says it is not an audit', async () => {
    renderAt('/periods/2/dashboard');
    const summary = await screen.findByText('What was checked');
    fireEvent.click(summary);
    const details = summary.closest('details');
    expect(details).toHaveTextContent('Net profit reconciles with the income statement lines — Failed.');
    expect(details).toHaveTextContent('Trial balance checks — Not applicable.');
    expect(details).toHaveTextContent('they are not an audit');
  });

  it('applies the rounding policy of a statement published in thousands', async () => {
    renderAt('/periods/2/data?mode=statement');
    const set = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
    await screen.findByLabelText('Total assets');
    set('Total assets', '1234000');
    set('Total liabilities', '600000');
    set('Total equity', '633000');
    const panel = () => screen.getByRole('heading', { name: 'Accounting identity' }).closest('section');
    // Exact figures: 1,000 out is an error.
    expect(panel()).toHaveTextContent('Out by MYR 1,000.00');
    // Figures from a report in RM'000: three rounded figures allow 1,500.
    fireEvent.change(screen.getByLabelText('The figures are'), { target: { value: '1000' } });
    expect(panel()).toHaveTextContent('The identity holds.');
    set('Total equity', '632400');
    expect(panel()).toHaveTextContent('They must agree to within 1,500.00');
  });

  it('asks for the closing stock count instead of assuming zero', async () => {
    const original = api.previewTrialBalance;
    api.previewTrialBalance = async (lines) => ({
      ...previewFor(lines.map((line) => ({ ...line, category: line.category || 'cash' }))),
      inventory: {
        method: 'periodic_unadjusted',
        label: 'Periodic inventory, not adjusted',
        explanation: 'Opening stock and purchases are charged to cost of sales, but the closing stock count has not been posted.',
        needs_closing_stock: !lines.some((line) => /period-end adjustment/i.test(line.account_name)),
        opening_balance_in_inventory: null,
      },
    });
    try {
      renderAt('/periods/2/data');
      await screen.findByRole('heading', { name: 'Trial balance' });
      fireEvent.change(screen.getByLabelText('Row 1 account name'), { target: { value: 'Opening stock' } });
      fireEvent.change(screen.getByLabelText('Row 1 debit'), { target: { value: '1000' } });
      const panel = await screen.findByLabelText('Period-end stock');
      expect(panel).toHaveTextContent('Periodic inventory, not adjusted');
      expect(panel).toHaveTextContent('Closing stock is not assumed to be zero');

      fireEvent.change(within(panel).getByLabelText(/Closing stock count/), { target: { value: '250' } });
      fireEvent.click(within(panel).getByRole('button', { name: 'Add closing stock' }));
      // Two visible, traceable adjustment rows: Dr inventory, Cr cost of sales.
      const added = screen.getAllByDisplayValue('Closing stock (period-end adjustment)');
      expect(added).toHaveLength(2);
      expect(screen.getAllByText(/Period-end adjustment: closing stock count of 250.00/)).toHaveLength(2);
    } finally {
      api.previewTrialBalance = original;
    }
  });
});

describe('roles: CEO / Admin and Finance Clerk', () => {
  const asClerk = () => {
    organisationState = { status: 'ready', organisation: COMPANY, candidates: [], role: 'clerk' };
  };
  const asAdmin = () => {
    organisationState = { status: 'ready', organisation: COMPANY, candidates: [], role: 'admin' };
  };

  it('a Finance Clerk starts on Financial Data and sees only the data pages', async () => {
    asClerk();
    try {
      renderAt('/');
      // The latest period by date (FY2025) opens for data entry.
      await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/periods/2/data'));
      const nav = await screen.findByRole('navigation', { name: 'Main' });
      expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual([
        'Financial Data', 'Financial History',
      ]);
      expect(screen.getByText('Finance Clerk')).toBeInTheDocument();
    } finally {
      asAdmin();
    }
  });

  it.each([
    ['/overview'],
    ['/periods/2/dashboard'],
    ['/analysis'],
    ['/settings'],
  ])('a Finance Clerk cannot open %s', async (path) => {
    asClerk();
    try {
      renderAt(path);
      expect(await screen.findByRole('heading', { name: 'Not available for your role' }))
        .toBeInTheDocument();
      expect(screen.queryByText('Overall score')).not.toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Go to Financial Data' })).toHaveAttribute('href', '/data');
    } finally {
      asAdmin();
    }
  });

  it('a Finance Clerk can edit periods but not delete them or open the dashboard', async () => {
    asClerk();
    try {
      renderAt('/history');
      expect(await screen.findByRole('button', { name: 'Edit period FY2024' })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Delete period/ })).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument();
      expect(screen.getAllByRole('link', { name: /Edit data|Enter data/ }).length).toBe(2);
    } finally {
      asAdmin();
    }
  });

  it('the CEO / Admin invites users with a single-use link and sees the activity log', async () => {
    const add = vi.fn(async (data) => ({
      id: 8, email: data.email, role: data.role, state: 'pending',
      created_at: '2026-11-25T10:00:00Z', expires_at: '2026-12-02T10:00:00Z', token: 'secret-token',
    }));
    memberCalls.add = add;
    try {
      renderAt('/settings');
      const section = (await screen.findByRole('heading', { name: 'Users and roles' })).closest('section');
      expect(section).toHaveTextContent('Crystalina Dibble');
      expect(section).toHaveTextContent('(you)');
      // The account that set the organisation up cannot be demoted or removed.
      expect(within(section).getByLabelText('Role of owner@example.com')).toBeDisabled();
      expect(within(section).queryByRole('button', { name: 'Remove owner@example.com' }))
        .not.toBeInTheDocument();
      // Invitations, with only pending ones revocable.
      expect(await within(section).findByText('new@example.com')).toBeInTheDocument();
      expect(within(section).getByRole('button', { name: 'Revoke the invitation for new@example.com' }))
        .toBeInTheDocument();
      expect(within(section).queryByRole('button', { name: 'Revoke the invitation for old@example.com' }))
        .not.toBeInTheDocument();

      fireEvent.change(within(section).getByLabelText('Email address'), {
        target: { value: 'another@example.com' },
      });
      fireEvent.click(within(section).getByRole('button', { name: /Create invitation/ }));
      await waitFor(() => expect(add).toHaveBeenCalledWith({ email: 'another@example.com', role: 'clerk' }));
      // The link is shown once, to send to the person.
      expect(await within(section).findByText(/\/join\?token=secret-token/)).toBeInTheDocument();

      fireEvent.click(within(section).getByRole('button', { name: 'Remove clerk@example.com' }));
      expect(screen.getByRole('alertdialog', { name: 'Remove Finance Clerk?' })).toHaveTextContent(
        'financial data they entered are kept',
      );

      const log = (await screen.findByRole('heading', { name: 'Activity log' })).closest('section');
      expect(await within(log).findByText('Corrected financial data')).toBeInTheDocument();
      expect(log).toHaveTextContent('FY2025, revision 1 → 2 (revenue)');
      expect(log).toHaveTextContent('clerk@example.com');
    } finally {
      memberCalls.add = async () => ({});
    }
  });

  it('the CEO / Admin sees every page in the navigation', async () => {
    renderAt('/overview');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getAllByRole('link')).toHaveLength(5);
    expect(screen.getByText('CEO / Admin')).toBeInTheDocument();
  });
});

describe('accepting an invitation', () => {
  it('shows what the invitation is for and joins only when accepted', async () => {
    const accept = vi.fn(async () => ({}));
    memberCalls.accept = accept;
    try {
      renderAt('/join?token=abc');
      expect(await screen.findByRole('button', { name: 'Accept and join CrystalCorps' })).toBeInTheDocument();
      expect(screen.getByText('Finance Clerk')).toBeInTheDocument();
      expect(accept).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole('button', { name: 'Accept and join CrystalCorps' }));
      await waitFor(() => expect(accept).toHaveBeenCalledWith('abc'));
    } finally {
      memberCalls.accept = async () => ({});
    }
  });

  it('cannot be accepted from a different email address', async () => {
    invitationPreview = { ...invitationPreview, email: 'someone.else@example.com' };
    try {
      renderAt('/join?token=abc');
      expect(await screen.findByText(/Sign in with someone.else@example.com to accept/))
        .toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Accept and join/ })).not.toBeInTheDocument();
    } finally {
      invitationPreview = { ...invitationPreview, email: 'owner@example.com' };
    }
  });

  it('says when an invitation has expired', async () => {
    invitationPreview = { ...invitationPreview, state: 'expired' };
    try {
      renderAt('/join?token=abc');
      expect(await screen.findByText(/This invitation has been expired/)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Accept and join/ })).not.toBeInTheDocument();
    } finally {
      invitationPreview = { ...invitationPreview, state: 'pending' };
    }
  });
});
