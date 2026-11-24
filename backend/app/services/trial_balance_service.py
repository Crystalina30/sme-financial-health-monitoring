"""Derive statement figures from a trial balance.

Accounting software such as Sage keeps the ledger and can export a trial
balance: every account with its debit or credit balance at the period end.
The figures the indicators need (revenue, cost of goods sold, current assets
and so on) are not rows in that export; they are sums of many rows. This
module does that step:

1. every account is assigned to one of the categories below;
2. each category is netted on its normal side (a debit-normal category is
   debits minus credits), so contra accounts such as sales returns,
   accumulated depreciation or closing stock reduce the total automatically;
3. the statement figures are built from the category totals with the
   formulas in ``FIGURE_FORMULAS``;
4. every figure keeps the list of accounts it came from, so the result can be
   traced back to the raw rows.

The trial balance is assumed to be taken **before closing entries**, which is
the form used to prepare financial statements: income and expense accounts
still hold the period's balances, and the profit for the period has not yet
been moved into retained earnings. Total equity is therefore the equity
accounts plus the period's net profit. When the trial balance balances, total
assets equal total liabilities plus equity by construction.
"""

import re
from dataclasses import dataclass, field

#: A trial balance must balance to the cent; anything else is a data error.
BALANCE_TOLERANCE = 0.005


@dataclass(frozen=True)
class Category:
    code: str
    label: str
    statement: str  # "income_statement" or "balance_sheet"
    normal_side: str  # "debit" or "credit"
    examples: str


CATEGORIES: tuple[Category, ...] = (
    Category("revenue", "Revenue", "income_statement", "credit",
             "Sales, service income; sales returns and discounts allowed reduce it"),
    Category("other_operating_income", "Other operating income", "income_statement",
             "credit", "Operating income that is not revenue: wage subsidies, grants, "
             "rental of spare premises"),
    Category("other_income", "Other income (non-operating)", "income_statement", "credit",
             "Interest and dividends received, gains on disposal of assets"),
    Category("other_expense", "Other expense (non-operating)", "income_statement", "debit",
             "Losses on disposal, impairment losses, exchange losses"),
    Category("cost_of_sales", "Cost of sales", "income_statement", "debit",
             "Purchases, carriage inwards, direct labour, opening stock; closing stock reduces it"),
    Category("operating_expense", "Operating expense", "income_statement", "debit",
             "Salaries, rent, utilities, marketing, depreciation, bank charges"),
    Category("interest_expense", "Interest expense", "income_statement", "debit",
             "Interest on loans, overdrafts and hire purchase"),
    Category("tax_expense", "Tax expense", "income_statement", "debit",
             "Income tax for the period"),
    Category("cash", "Cash and bank", "balance_sheet", "debit",
             "Bank accounts, petty cash, short-term deposits"),
    Category("accounts_receivable", "Trade receivables", "balance_sheet", "debit",
             "Trade debtors; the allowance for doubtful debts reduces it"),
    Category("inventory", "Inventory", "balance_sheet", "debit",
             "Closing stock of goods, raw materials and work in progress"),
    Category("other_current_asset", "Other current asset", "balance_sheet", "debit",
             "Prepayments, deposits paid, other receivables"),
    Category("non_current_asset", "Non-current asset", "balance_sheet", "debit",
             "Property, equipment, vehicles; accumulated depreciation reduces it"),
    Category("current_liability", "Current liability", "balance_sheet", "credit",
             "Trade creditors, accruals, overdraft, tax payable, loans due within a year"),
    Category("non_current_liability", "Non-current liability", "balance_sheet", "credit",
             "Term loans and hire purchase due after a year"),
    Category("equity", "Share capital and reserves", "balance_sheet", "credit",
             "Share capital, owner's capital, reserves; drawings and dividends reduce it"),
    Category("retained_earnings", "Retained earnings (brought forward)", "balance_sheet",
             "credit", "Accumulated profits from earlier periods"),
)

CATEGORY_BY_CODE = {category.code: category for category in CATEGORIES}

#: How each statement figure is built. Category names refer to the netted
#: category totals; figure names refer to figures defined above them.
FIGURE_FORMULAS: dict[str, str] = {
    "revenue": "Σ Revenue accounts (credit − debit)",
    "cost_of_goods_sold": "Σ Cost of sales accounts (debit − credit)",
    "operating_expenses": "Σ Operating expense accounts (debit − credit)",
    "interest_expense": "Σ Interest expense accounts (debit − credit)",
    "tax_expense": "Σ Tax expense accounts (debit − credit)",
    "gross_profit": "Revenue − Cost of goods sold",
    "other_operating_income": "Σ Other operating income accounts (credit − debit)",
    "other_income": "Σ Other (non-operating) income accounts (credit − debit)",
    "other_expenses": "Σ Other (non-operating) expense accounts (debit − credit)",
    "operating_profit": "Gross profit + Other operating income − Operating expenses",
    "net_profit": "Operating profit + Other income − Other expenses − Interest − Tax",
    "cash_and_equivalents": "Σ Cash and bank accounts (debit − credit)",
    "accounts_receivable": "Σ Trade receivable accounts (debit − credit)",
    "inventory": "Σ Inventory accounts (debit − credit); not reported when there are none",
    "other_current_assets": "Σ Other current asset accounts (debit − credit)",
    "current_assets": "Cash + Trade receivables + Inventory + Other current assets",
    "non_current_assets": "Σ Non-current asset accounts (debit − credit)",
    "total_assets": "Current assets + Non-current assets",
    "current_liabilities": "Σ Current liability accounts (credit − debit)",
    "non_current_liabilities": "Σ Non-current liability accounts (credit − debit)",
    "total_liabilities": "Current liabilities + Non-current liabilities",
    "total_equity": "Share capital and reserves + Retained earnings b/f + Net profit",
    "retained_earnings": "Retained earnings b/f + Net profit; not reported when there are none",
}

#: Figures taken straight from one category, and the category behind each.
_DIRECT = {
    "revenue": "revenue",
    "cost_of_goods_sold": "cost_of_sales",
    "operating_expenses": "operating_expense",
    "interest_expense": "interest_expense",
    "tax_expense": "tax_expense",
    "other_operating_income": "other_operating_income",
    "other_income": "other_income",
    "other_expenses": "other_expense",
    "cash_and_equivalents": "cash",
    "accounts_receivable": "accounts_receivable",
    "inventory": "inventory",
    "other_current_assets": "other_current_asset",
    "non_current_assets": "non_current_asset",
    "current_liabilities": "current_liability",
    "non_current_liabilities": "non_current_liability",
}

#: Figures summed from several categories (sign +1 adds, -1 subtracts).
_COMPOSITE = {
    "gross_profit": (("revenue", 1), ("cost_of_sales", -1)),
    "operating_profit": (
        ("revenue", 1), ("cost_of_sales", -1), ("other_operating_income", 1),
        ("operating_expense", -1),
    ),
    "net_profit": (
        ("revenue", 1), ("cost_of_sales", -1), ("other_operating_income", 1),
        ("operating_expense", -1), ("other_income", 1), ("other_expense", -1),
        ("interest_expense", -1), ("tax_expense", -1),
    ),
    "current_assets": (
        ("cash", 1), ("accounts_receivable", 1), ("inventory", 1), ("other_current_asset", 1),
    ),
    "total_assets": (
        ("cash", 1), ("accounts_receivable", 1), ("inventory", 1),
        ("other_current_asset", 1), ("non_current_asset", 1),
    ),
    "total_liabilities": (("current_liability", 1), ("non_current_liability", 1)),
}

#: The figures a financial record stores. The others (gross profit, operating
#: profit, the non-current totals) are shown for transparency only.
RECORD_FIELDS = (
    "revenue", "cost_of_goods_sold", "operating_expenses", "interest_expense", "tax_expense",
    "net_profit", "other_operating_income", "other_income", "other_expenses",
    "cash_and_equivalents", "accounts_receivable", "inventory",
    "current_assets", "total_assets", "current_liabilities", "total_liabilities",
    "total_equity", "retained_earnings",
)

#: Account names that legitimately sit on the opposite side to their
#: category (contra accounts), so an opposite balance is not flagged.
_CONTRA_NAMES = re.compile(
    r"return|discount|allowance|provision|accumulated|depreciation|impairment|"
    r"closing (stock|inventory)|drawing|dividend|loss|write[- ]?(off|down)|rebate|"
    r"round[- ]?off|exchange",
    re.IGNORECASE,
)
_OPENING_STOCK = re.compile(r"opening (stock|inventory)", re.IGNORECASE)
_CLOSING_STOCK = re.compile(
    r"closing (stock|inventory)|(stock|inventory)\W*\(?closing", re.IGNORECASE
)
_COST_OF_SALES_ACCOUNT = re.compile(r"cost of (goods sold|sales)|\bcogs\b", re.IGNORECASE)
_PURCHASES = re.compile(r"purchase", re.IGNORECASE)

_MIXED_REVIEWED = re.compile(r"cost of sales reviewed", re.IGNORECASE)

#: Rows added in the app as period-end adjustments (a stock count, or a
#: confirmation that there was none) carry a source reference starting with
#: this, so they are traceable and distinguishable from imported rows.
ADJUSTMENT_REF = "Period-end adjustment"


@dataclass(frozen=True)
class InventoryTreatment:
    """How the trial balance accounts for stock, as far as it can be told.

    method:
      none                   no stock or cost-of-sales accounts (e.g. services)
      perpetual              cost of sales recorded directly as goods are sold;
                             the inventory account holds closing stock
      periodic_adjusted      opening stock + purchases, with closing stock
                             credited to cost of sales and held as an asset
      periodic_unadjusted    opening stock charged to cost of sales, but no
                             closing stock posted: the count is needed
      periodic_opening_in_inventory
                             purchases charged, no opening/closing entries, and
                             an inventory balance that is most likely the
                             opening stock: an unadjusted periodic trial balance
      purchases_only         purchases charged and no stock accounts at all
    """

    method: str
    label: str
    explanation: str
    needs_closing_stock: bool = False
    # The account mapping needs an accountant's review (mixed postings).
    needs_review: bool = False
    # For periodic_opening_in_inventory: the balance that must move to cost
    # of sales before the closing count is booked.
    opening_balance_in_inventory: float | None = None

_INCOME_CATEGORIES = tuple(c.code for c in CATEGORIES if c.statement == "income_statement")

#: Figures that may not be negative, because the record schema rejects them.
_NON_NEGATIVE = {
    "revenue": "Revenue",
    "cost_of_goods_sold": "Cost of goods sold",
    "operating_expenses": "Operating expenses",
    "interest_expense": "Interest expense",
    "cash_and_equivalents": "Cash and equivalents",
    "accounts_receivable": "Trade receivables",
    "inventory": "Inventory",
    "current_assets": "Current assets",
    "total_assets": "Total assets",
    "current_liabilities": "Current liabilities",
    "total_liabilities": "Total liabilities",
}


@dataclass(frozen=True)
class Line:
    """One trial balance row, as submitted."""

    line_number: int
    account_code: str
    account_name: str
    debit: float
    credit: float
    category: str | None
    account_group: str = ""
    source_ref: str = ""


@dataclass
class Contribution:
    line_number: int
    account_code: str
    account_name: str
    category: str
    amount: float  # signed effect on the figure
    source_ref: str = ""


@dataclass
class Figure:
    value: float | None
    formula: str
    contributions: list[Contribution] = field(default_factory=list)


@dataclass
class Derivation:
    figures: dict[str, Figure]
    category_totals: dict[str, float]
    total_debit: float
    total_credit: float
    errors: list[str]
    warnings: list[str]
    # Each warning with its severity and a code: (severity, code, message).
    # "material" findings make an assessment provisional; "info" ones do not.
    findings: list[tuple[str, str, str]] = field(default_factory=list)
    inventory: InventoryTreatment | None = None

    @property
    def difference(self) -> float:
        return round(self.total_debit - self.total_credit, 2)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def values(self) -> dict[str, float | None]:
        return {name: figure.value for name, figure in self.figures.items()}

    def record_values(self) -> dict[str, float | None]:
        """Only the figures a financial record stores."""
        return {name: self.figures[name].value for name in RECORD_FIELDS}


def _net(line: Line, category: Category) -> float:
    """A line's balance on its category's normal side."""
    if category.normal_side == "debit":
        return line.debit - line.credit
    return line.credit - line.debit


def derive(lines: list[Line]) -> Derivation:
    """Calculate the statement figures from trial balance rows."""
    errors: list[str] = []
    warnings: list[str] = []
    findings: list[tuple[str, str, str]] = []

    def note(severity: str, code: str, message: str) -> None:
        warnings.append(message)
        findings.append((severity, code, message))

    total_debit = round(sum(line.debit for line in lines), 2)
    total_credit = round(sum(line.credit for line in lines), 2)

    if not lines:
        errors.append("The trial balance has no rows.")
    if abs(total_debit - total_credit) > BALANCE_TOLERANCE:
        errors.append(
            f"The trial balance does not balance: debits {total_debit:,.2f}, "
            f"credits {total_credit:,.2f}, difference {total_debit - total_credit:,.2f}."
        )

    for line in lines:
        if line.debit < 0 or line.credit < 0:
            errors.append(
                f"Row {line.line_number} ({line.account_name}): debit and credit must not "
                "be negative. Enter a negative balance on the other side."
            )
        if line.category is None:
            errors.append(f"Row {line.line_number} ({line.account_name}) has no category.")
        elif line.category not in CATEGORY_BY_CODE:
            errors.append(
                f"Row {line.line_number} ({line.account_name}) has an unknown category "
                f"'{line.category}'."
            )

    codes = [line.account_code for line in lines if line.account_code]
    duplicates = sorted({code for code in codes if codes.count(code) > 1})
    if duplicates:
        note(
            "material", "duplicate_account_code",
            "Account code used on more than one row: " + ", ".join(duplicates)
            + ". Check that no account was entered twice."
        )

    # Net every categorised line on its category's normal side.
    by_category: dict[str, list[Contribution]] = {c.code: [] for c in CATEGORIES}
    for line in lines:
        category = CATEGORY_BY_CODE.get(line.category or "")
        if category is None:
            continue
        by_category[category.code].append(
            Contribution(line.line_number, line.account_code, line.account_name,
                         category.code, round(_net(line, category), 2), line.source_ref)
        )
    totals = {code: round(sum(c.amount for c in items), 2) for code, items in by_category.items()}

    figures: dict[str, Figure] = {}
    for name, category_code in _DIRECT.items():
        figures[name] = Figure(totals[category_code], FIGURE_FORMULAS[name],
                               list(by_category[category_code]))
    for name, parts in _COMPOSITE.items():
        contributions = [
            Contribution(c.line_number, c.account_code, c.account_name, c.category,
                         round(c.amount * sign, 2), c.source_ref)
            for category_code, sign in parts
            for c in by_category[category_code]
        ]
        value = round(sum(totals[code] * sign for code, sign in parts), 2)
        figures[name] = Figure(value, FIGURE_FORMULAS[name], contributions)

    net_profit = figures["net_profit"].value
    equity_parts = by_category["equity"] + by_category["retained_earnings"]
    figures["total_equity"] = Figure(
        round(totals["equity"] + totals["retained_earnings"] + net_profit, 2),
        FIGURE_FORMULAS["total_equity"],
        list(equity_parts) + figures["net_profit"].contributions,
    )

    # Optional figures: "not reported" is different from zero.
    if not by_category["inventory"]:
        figures["inventory"].value = None
    if by_category["retained_earnings"]:
        figures["retained_earnings"] = Figure(
            round(totals["retained_earnings"] + net_profit, 2),
            FIGURE_FORMULAS["retained_earnings"],
            list(by_category["retained_earnings"]) + figures["net_profit"].contributions,
        )
    else:
        figures["retained_earnings"] = Figure(None, FIGURE_FORMULAS["retained_earnings"])

    for name, label in _NON_NEGATIVE.items():
        value = figures[name].value
        if value is not None and value < -BALANCE_TOLERANCE:
            errors.append(
                f"{label} works out negative ({value:,.2f}). Check the categories and the "
                "debit/credit side of its accounts."
            )

    # An account on the opposite side to its category is often a mistake in
    # the category or in the export (a sales account with a debit balance).
    # Contra accounts are expected to be opposite and are not flagged.
    opposite = [
        c for items in by_category.values() for c in items
        if c.amount < -BALANCE_TOLERANCE and not _CONTRA_NAMES.search(c.account_name)
    ]
    if opposite:
        note(
            "material", "opposite_side_balance",
            "These accounts have a balance on the opposite side to their category's normal "
            "side; check the category and the debit/credit columns: "
            + "; ".join(
                f"row {c.line_number} {c.account_name} "
                f"({CATEGORY_BY_CODE[c.category].label}, {c.amount:,.2f})"
                for c in opposite[:6]
            )
            + ("; ..." if len(opposite) > 6 else "")
            + "."
        )

    inventory = _inventory_treatment(by_category, totals, note)

    if lines and not by_category["revenue"]:
        note("info", "no_revenue_account", "No account is categorised as revenue.")
    if lines and all(totals[code] == 0 for code in _INCOME_CATEGORIES):
        note(
            "material", "post_closing_trial_balance",
            "All income and expense accounts are zero. This looks like a trial balance "
            "taken after closing entries; use the one taken before closing, or the period's "
            "profit will be missing."
        )
    return Derivation(
        figures, totals, total_debit, total_credit, errors, warnings, findings, inventory
    )


def _inventory_treatment(by_category, totals, note) -> InventoryTreatment:
    """Work out how stock is accounted for, and what is missing.

    Nothing is inferred from an account being absent. In particular:

    * closing stock is never assumed to be zero: a periodic trial balance
      needs the period-end count, or an explicit confirmation that there was
      none, before its cost of goods sold is accepted;
    * purchases with no stock accounts at all do not prove that no stock is
      held, so they need the same count or confirmation;
    * a cost-of-goods-sold account mixed with purchases may count the same
      goods twice, so it needs an accountant's review (recategorise, or
      confirm explicitly that they are separate costs).

    Counts and confirmations are entered in the app as visible adjustment
    rows (``ADJUSTMENT_REF``) and saved, with who entered them, in the audit
    trail.
    """
    cos = by_category["cost_of_sales"]
    inventory_rows = by_category["inventory"]
    opening = [c for c in cos if _OPENING_STOCK.search(c.account_name) and c.amount]
    closing_rows = [c for c in cos if _CLOSING_STOCK.search(c.account_name)]
    closing_credit = round(sum(-c.amount for c in closing_rows if c.amount < 0), 2)
    adjustments = [c for c in cos + inventory_rows if c.source_ref.startswith(ADJUSTMENT_REF)]
    confirmed_nil = [c for c in closing_rows if c.source_ref.startswith(ADJUSTMENT_REF)
                     and not c.amount]
    mixed_confirmed = [c for c in adjustments if _MIXED_REVIEWED.search(c.account_name)]
    direct = [c for c in cos if _COST_OF_SALES_ACCOUNT.search(c.account_name)]
    purchases = [c for c in cos if _PURCHASES.search(c.account_name) and c.amount]
    inventory_total = totals["inventory"]
    stated_nil = [c for c in inventory_rows if _CLOSING_STOCK.search(c.account_name)
                  and not c.amount]
    adjusted = closing_credit > 0 or bool(confirmed_nil)

    if not cos and not inventory_rows:
        return InventoryTreatment(
            "none", "No stock accounts",
            "There are no cost-of-sales or inventory accounts, as in a service business.")

    # Direct cost of goods sold together with purchases: possible double count.
    if direct and purchases:
        if mixed_confirmed:
            note("info", "mixed_cost_of_sales_reviewed",
                 "Purchases and cost-of-goods-sold postings were confirmed as separate costs "
                 "by the user (period-end adjustment).")
            return InventoryTreatment(
                "mixed_reviewed", "Cost of sales and purchases (reviewed)",
                "Cost of goods sold is recorded directly and purchases are charged as well; "
                "the user confirmed these are separate costs.")
        note("material", "mixed_cost_of_sales",
             "Both a cost-of-goods-sold account ("
             + ", ".join(c.account_name for c in direct[:3])
             + ") and purchases ("
             + ", ".join(c.account_name for c in purchases[:3])
             + ") are charged to cost of sales. In a perpetual system purchases go to "
             "inventory and are already in cost of goods sold, so this would count the same "
             "goods twice; in a periodic system there is normally no separate cost-of-goods-"
             "sold account. An accountant should recategorise the purchases (to inventory) "
             "or confirm that they are separate costs.")
        return InventoryTreatment(
            "mixed_unreviewed", "Cost of sales and purchases (needs review)",
            "Direct cost-of-goods-sold postings and purchases are both charged; this may "
            "double count.", needs_review=True)

    if direct:
        note("info", "perpetual_inventory",
             "Cost of sales is recorded directly (perpetual inventory or an already adjusted "
             "trial balance), so no stock adjustment is needed.")
        return InventoryTreatment(
            "perpetual", "Perpetual inventory / cost of sales recognised",
            "Cost of sales is recorded as goods are sold; the inventory account holds the "
            "closing stock.")

    # From here on, cost of sales is built from opening stock and purchases:
    # a periodic system, which needs the closing count.
    if adjusted:
        treatment = InventoryTreatment(
            "periodic_adjusted", "Periodic inventory, adjusted",
            "Cost of goods sold = opening stock + purchases and direct costs − closing "
            f"stock ({closing_credit:,.2f}).")
        if confirmed_nil and closing_credit == 0:
            note("info", "closing_stock_confirmed_nil",
                 "Closing stock was confirmed as nil by the user (period-end adjustment).")
        elif abs(closing_credit - inventory_total) > BALANCE_TOLERANCE:
            note("material", "closing_stock_mismatch",
                 f"Closing stock credited to cost of sales ({closing_credit:,.2f}) differs "
                 f"from the inventory balance ({inventory_total:,.2f}). They should be "
                 "the same stock count.")
        return treatment

    if opening:
        where = (
            f" The trial balance shows closing stock as nil ({stated_nil[0].account_name}, "
            f"row {stated_nil[0].line_number}) without crediting cost of sales, which is not "
            "a stock count." if stated_nil else ""
        )
        note("material", "missing_closing_stock",
             "Periodic inventory: opening stock is charged to cost of sales, but there is no "
             f"closing stock entry.{where} Cost of goods sold would then assume every unit "
             "was sold. Enter the period-end stock count, or confirm there was no stock.")
        return InventoryTreatment(
            "periodic_unadjusted", "Periodic inventory, not adjusted",
            "Opening stock and purchases are charged to cost of sales, but the closing stock "
            "count has not been posted.", needs_closing_stock=True)

    if inventory_total > 0:
        note("material", "inventory_may_be_opening_stock",
             "Purchases are charged to cost of sales, but there is no opening or closing "
             f"stock entry and the inventory account holds {inventory_total:,.2f}. In an "
             "unadjusted periodic trial balance that is the opening stock, so both cost of "
             "goods sold and inventory would be wrong. Enter the period-end stock count to "
             "adjust them.")
        return InventoryTreatment(
            "periodic_opening_in_inventory", "Periodic inventory, not adjusted (likely)",
            "The inventory balance is probably the opening stock; it must move to cost of "
            "sales and be replaced by the closing count.",
            needs_closing_stock=True, opening_balance_in_inventory=inventory_total)

    # Purchases and no stock accounts: that does not show that nothing is left.
    note("material", "stock_not_confirmed",
         "Purchases are charged to cost of sales, but there are no stock accounts, so the "
         "trial balance does not show whether any goods were still on hand at the period "
         "end. Cost of goods sold would include them. Enter the period-end stock count, or "
         "confirm there was no stock.")
    return InventoryTreatment(
        "purchases_only", "Purchases with no stock accounts",
        "Purchases are expensed and there are no stock accounts; the closing stock must be "
        "counted or confirmed as nil.", needs_closing_stock=True)

# ---------------------------------------------------------------------------
# Category suggestions
# ---------------------------------------------------------------------------

#: Keyword rules for suggesting a category from an account name. They are
#: checked in order, so the more specific phrases come first (for example
#: "accumulated depreciation" before "depreciation", "interest received"
#: before "interest"). A suggestion is only a starting point: the user
#: confirms every category before the figures are calculated.
_KEYWORD_RULES: tuple[tuple[str, str], ...] = (
    (r"loss on (disposal|sale)|impairment loss|(foreign )?exchange loss|donation",
     "other_expense"),
    (r"wage subsid|government (grant|subsid)|grant income|subsidy income",
     "other_operating_income"),
    (r"accumulated depreciation|accum\.? dep|provision for depreciation", "non_current_asset"),
    (r"doubtful debt|bad debt provision|allowance for (credit|expected)", "accounts_receivable"),
    (r"opening (stock|inventory)|closing (stock|inventory)", "cost_of_sales"),
    (r"retained (profit|earning)|accumulated (profit|loss)|profit and loss reserve|"
     r"unappropriated profit", "retained_earnings"),
    (r"interest (received|income|earned)|dividend (received|income)|rental income|"
     r"other income|gain on|discount received|sundry income", "other_income"),
    (r"(income )?tax (payable|provision)|provision for tax|(sst|gst|vat|sales tax) "
     r"(payable|control|output)|output tax", "current_liability"),
    (r"income tax|taxation|tax expense|corporate tax", "tax_expense"),
    (r"interest", "interest_expense"),
    (r"short[- ]term loan|overdraft", "current_liability"),
    (r"term loan|long[- ]term|non[- ]current|hire purchase|debenture|mortgage",
     "non_current_liability"),
    (r"overdraft|creditor|payable|accrual|accrued|short[- ]term loan|deposit received|"
     r"deferred income|dividend payable|epf payable|socso payable", "current_liability"),
    (r"\bloan", "non_current_liability"),
    (r"share capital|ordinary shares|capital account|owner.?s capital|^capital$|drawing|"
     r"reserve|dividend (paid|declared)", "equity"),
    (r"debtor|receivable", "accounts_receivable"),
    (r"stock|inventor|raw material|work in progress|finished goods", "inventory"),
    (r"prepa(id|yment)|deposit|advance to|input tax|other current", "other_current_asset"),
    (r"bank charge|bank fee|expense|running cost|upkeep", "operating_expense"),
    (r"bank|cash|petty", "cash"),
    (r"land|building|propert|equipment|machinery|plant|vehicle|motor|furniture|fixture|"
     r"fitting|computer|renovation|goodwill|intangible|investment", "non_current_asset"),
    (r"purchase|cost of (sales|goods)|carriage in|\bdirect (labour|labor|material|cost)|"
     r"freight in|import duty", "cost_of_sales"),
    (r"sales return|returns inward|discount allowed|sales|revenue|turnover|fees earned|"
     r"service income|commission income", "revenue"),
    (r"salar|wage|staff|epf|socso|\beis\b|bonus|\brent|utilit|electric|water|telephone|internet|"
     r"insurance|advertis|marketing|repair|maintenance|depreciation|amorti|office|travel|"
     r"professional|audit|legal|accounting fee|bank charge|stationery|postage|"
     r"entertainment|commission|carriage out|subscription|licen|cleaning|security|"
     r"training|printing|general expense|admin|sundry|miscellaneous|expense", "operating_expense"),
)


def suggest_category(account_name: str) -> str | None:
    """Suggest a category from the account name, or None if nothing matches."""
    name = account_name.strip().lower()
    for pattern, category in _KEYWORD_RULES:
        if re.search(pattern, name):
            return category
    return None


#: Account groups or types as exported by accounting packages, checked in
#: order. They cover Tally's predefined groups (Sales Accounts, Sundry
#: Debtors, Duties & Taxes, ...) and type names used by packages such as Sage
#: and Xero (Current Asset, Fixed Asset, Overheads, ...). "SIDE" means the
#: group holds both assets and liabilities, so the balance decides.
_GROUP_RULES: tuple[tuple[str, str], ...] = (
    (r"suspense", "NONE"),
    (r"bank od|overdraft", "current_liability"),
    (r"sales account|^sales$|^revenue$|^income$|^turnover$|operating revenue|trading income",
     "revenue"),
    (r"\bdirect income|\bindirect income|other income|non[- ]operating income", "other_income"),
    (r"purchase account|\bdirect expense|cost of (sales|goods)|\bdirect cost|^purchases$",
     "cost_of_sales"),
    (r"indirect expense|overhead|^expenses?$|operating expense|administrative|"
     r"selling|distribution|depreciation", "operating_expense"),
    (r"bank account|cash[- ]in[- ]hand|^bank$|^cash$|cash and (bank|cash equivalents)",
     "cash"),
    (r"sundry debtor|trade debtor|accounts receivable|^receivables?$", "accounts_receivable"),
    (r"stock[- ]in[- ]hand|^inventor|^stock$", "inventory"),
    (r"duties|taxes|provision", "SIDE"),
    (r"sundry creditor|trade creditor|accounts payable|^payables?$|current liabilit",
     "current_liability"),
    (r"secured loan|unsecured loan|loans? \(liability\)|non[- ]current liabilit|"
     r"long[- ]term liabilit|term liabilit", "non_current_liability"),
    (r"fixed asset|non[- ]current asset|investment|property|plant|intangible",
     "non_current_asset"),
    (r"deposits? \(asset\)|loans? (&|and) advances|prepayment|current asset|misc",
     "other_current_asset"),
    (r"reserves|retained|profit (&|and) loss", "retained_earnings"),
    (r"capital|equity|share", "equity"),
)

#: A name may make a group's category more specific within the same part of
#: the statements: an "Indirect Expenses" account named "Bank interest" is
#: interest expense; a "Current Assets" account named "Stock" is inventory.
_REFINEMENTS = {
    "other_current_asset": {"cash", "accounts_receivable", "inventory"},
    "operating_expense": {"interest_expense", "tax_expense", "other_expense"},
    "other_income": {"other_operating_income"},
    "equity": {"retained_earnings"},
    "retained_earnings": {"equity"},
}

#: For a group that holds both sides (duties and taxes, provisions), a name
#: that clearly says which side wins over the balance.
_SIDE_NAMES = (
    (re.compile(r"\binput\b|receivable|refund|prepaid|advance", re.IGNORECASE),
     "other_current_asset"),
    (re.compile(r"\boutput\b|payable|provision for", re.IGNORECASE), "current_liability"),
)


def suggest(
    account_name: str, account_group: str = "", debit: float = 0.0, credit: float = 0.0
) -> tuple[str | None, str | None]:
    """Suggest a category and say what it was based on.

    The account group, when the export has one, decides first because it is
    the bookkeeper's own classification. The name can refine it within the
    same part of the statements. Without a usable group, the name decides.
    Returns (category, basis); basis is "account_group", "account_name" or
    None when there is no suggestion.
    """
    by_name = suggest_category(account_name)
    group = account_group.strip().lower()
    if group:
        for pattern, category in _GROUP_RULES:
            if not re.search(pattern, group):
                continue
            if category == "NONE":
                return None, None
            if category == "SIDE":
                for name_pattern, side_category in _SIDE_NAMES:
                    if name_pattern.search(account_name):
                        return side_category, "account_group"
                if debit - credit > 0:
                    return "other_current_asset", "account_group"
                return "current_liability", "account_group"
            if by_name in _REFINEMENTS.get(category, set()):
                return by_name, "account_group"
            return category, "account_group"
    if by_name:
        return by_name, "account_name"
    return None, None
