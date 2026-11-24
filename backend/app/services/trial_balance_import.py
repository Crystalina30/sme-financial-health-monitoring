"""Reading a trial balance from an exported file.

Accounting packages export trial balances in many layouts, so nothing here is
written for one package or one file:

* **Formats.** CSV (comma, semicolon or tab separated) and Excel ``.xlsx``.
  Every worksheet of a workbook is examined.
* **Finding the table.** Report titles above the table are skipped; the header
  row is found by its column names (``Account code``, ``Ledger``, ``Debit``,
  ``Dr``, ``Group`` and so on).
* **Amounts.** Either separate debit and credit columns, or one balance
  column, signed or marked ``Dr``/``Cr`` (as Tally prints it). Thousands
  separators, currency codes and brackets for negatives are understood. A
  negative debit is moved to the credit side and vice versa.
* **Groups.** An optional group/type column (Tally's "Group", Sage's or
  Xero's account type) is kept, because it is the best evidence for the
  account's category.
* **Skipped rows.** Total rows and blank rows are skipped and counted.
* **Traceability.** Every line keeps a reference to the file, sheet and row
  it came from.

Nothing is changed in the uploaded file; it is only read.
"""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, field

#: Uploads larger than this are refused; a trial balance is small.
MAX_FILE_BYTES = 5 * 1024 * 1024
#: The header is looked for in the first rows of each sheet.
HEADER_SEARCH_ROWS = 40


class ImportFileError(ValueError):
    """The file cannot be read at all (wrong type, corrupt, too large)."""


def _normalise_header(text: object) -> str:
    value = "" if text is None else str(text)
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value.rstrip(":.").strip()


_HEADER_PATTERNS: dict[str, re.Pattern] = {
    "code": re.compile(
        r"^((account|a/c|ledger|gl|nominal)\s*)?(code|no|number|ref|reference|#)$|"
        r"^nominal$|^n/c$"
    ),
    "name": re.compile(
        r"^((account|ledger|a/c|gl)\s*)?(name|description|title|head)$|"
        r"^(account|ledger|ledger account|particulars|details?|description|account head)$"
    ),
    "group": re.compile(
        r"^(group|under|parent|parent group|primary group|classification|class|type|"
        r"account (group|type|class)|ledger group)$"
    ),
    "debit": re.compile(
        r"^(closing\s+)?(debit|dr)(\s+(balance|amount))?(\s*\(.*\))?$"
    ),
    "credit": re.compile(
        r"^(closing\s+)?(credit|cr)(\s+(balance|amount))?(\s*\(.*\))?$"
    ),
    "balance": re.compile(
        r"^(closing\s+|net\s+)?(balance|amount)(\s*\(.*\))?$"
    ),
    "category": re.compile(r"^category$"),
}

_TOTAL_ROW = re.compile(r"^(grand\s+)?totals?\b|^total\s*:?$", re.IGNORECASE)
_DR_CR_SUFFIX = re.compile(r"^(.*?)\s*\b(dr|cr)\.?$", re.IGNORECASE)


@dataclass
class ImportedLine:
    account_code: str
    account_name: str
    account_group: str
    debit: float
    credit: float
    category: str | None
    source_ref: str


@dataclass
class SheetImport:
    name: str
    header_row: int | None
    columns: dict[str, str] = field(default_factory=dict)
    lines: list[ImportedLine] = field(default_factory=list)
    skipped_rows: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_debit(self) -> float:
        return round(sum(line.debit for line in self.lines), 2)

    @property
    def total_credit(self) -> float:
        return round(sum(line.credit for line in self.lines), 2)

    @property
    def usable(self) -> bool:
        return self.header_row is not None and bool(self.lines)


@dataclass
class FileImport:
    file_name: str
    file_type: str
    sheets: list[SheetImport]
    selected_sheet: str | None


# ---------------------------------------------------------------------------
# Amounts
# ---------------------------------------------------------------------------


def parse_amount(value: object) -> float | None:
    """Read an amount; None means the cell is not a number.

    Blank cells and a lone dash are zero. ``(1,000)`` and ``-1,000`` are
    negative. A leading currency code or symbol is ignored.
    """
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    text = str(value).strip()
    if text in ("", "-", "—", "–"):
        return 0.0
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1].strip()
    text = re.sub(r"^([A-Za-z]{2,3}|[$£€¥₹])\s*", "", text)
    text = re.sub(r"[\s,]", "", text)
    if text.startswith("-"):
        negative, text = not negative, text[1:]
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):  # "inf", "nan", or too large to represent
        return None
    return -number if negative else number


def parse_balance(value: object) -> tuple[float, float] | None:
    """Split a single balance into (debit, credit).

    ``1,000 Dr`` is a debit and ``1,000 Cr`` a credit. Without a marker, a
    positive balance is a debit and a negative one a credit, which is the
    usual export convention.
    """
    side = None
    if isinstance(value, str):
        match = _DR_CR_SUFFIX.match(value.strip())
        if match:
            value, side = match.group(1), match.group(2).lower()
    amount = parse_amount(value)
    if amount is None:
        return None
    if side == "cr":
        amount = -abs(amount)
    elif side == "dr":
        amount = abs(amount)
    return (amount, 0.0) if amount >= 0 else (0.0, -amount)


# ---------------------------------------------------------------------------
# Reading rows from a file
# ---------------------------------------------------------------------------


def _rows_from_csv(data: bytes) -> list[list[object]]:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return [list(row) for row in csv.reader(io.StringIO(text), dialect)]


def _rows_from_xlsx(data: bytes) -> tuple[dict[str, list[list[object]]], dict[str, int]]:
    """Every sheet's cell values, and how many formulas have no saved result."""
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise ImportFileError("Excel import is not available on this server.") from exc
    try:
        values = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        formulas = openpyxl.load_workbook(io.BytesIO(data), data_only=False, read_only=True)
    except Exception as exc:  # openpyxl raises several types for a bad file
        raise ImportFileError(
            "The Excel file could not be read. Save it as .xlsx (Excel 2007 or later) "
            "or export it as CSV."
        ) from exc

    sheets: dict[str, list[list[object]]] = {}
    unsaved: dict[str, int] = {}
    for sheet_name in values.sheetnames:
        value_rows = [list(row) for row in values[sheet_name].iter_rows(values_only=True)]
        formula_rows = formulas[sheet_name].iter_rows(values_only=True)
        missing = 0
        for value_row, formula_row in zip(value_rows, formula_rows):
            for cached, raw in zip(value_row, formula_row):
                if cached is None and isinstance(raw, str) and raw.startswith("="):
                    missing += 1
        sheets[sheet_name] = value_rows
        unsaved[sheet_name] = missing
    values.close()
    formulas.close()
    return sheets, unsaved


# ---------------------------------------------------------------------------
# Finding and reading the table
# ---------------------------------------------------------------------------


def _find_header(rows: list[list[object]]) -> tuple[int, dict[str, int]] | None:
    for index, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        columns: dict[str, int] = {}
        for column, cell in enumerate(row):
            text = _normalise_header(cell)
            if not text:
                continue
            for key, pattern in _HEADER_PATTERNS.items():
                if key not in columns and pattern.match(text):
                    columns[key] = column
                    break
        has_amounts = ("debit" in columns and "credit" in columns) or "balance" in columns
        if "name" in columns and has_amounts:
            if "debit" in columns and "credit" in columns:
                columns.pop("balance", None)
            return index, columns
    return None


def _cell(row: list[object], column: int | None) -> object:
    if column is None or column >= len(row):
        return None
    return row[column]


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return re.sub(r"\s+", " ", str(value)).strip()


def read_table(
    rows: list[list[object]],
    sheet_name: str,
    file_name: str,
    category_lookup: dict[str, str] | None = None,
) -> SheetImport:
    """Read the trial balance table from the rows of one sheet."""
    result = SheetImport(name=sheet_name, header_row=None)
    header = _find_header(rows)
    if header is None:
        result.errors.append(
            "No header row with an account name column and debit/credit (or balance) "
            "columns was found."
        )
        return result

    header_index, columns = header
    result.header_row = header_index + 1
    result.columns = {key: _text(rows[header_index][col]) for key, col in columns.items()}
    lookup = category_lookup or {}
    where = file_name if sheet_name == "CSV" else f"{file_name} › {sheet_name}"

    for offset, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        name = _text(_cell(row, columns.get("name")))
        code = _text(_cell(row, columns.get("code")))
        group = _text(_cell(row, columns.get("group")))

        if not any(_text(cell) for cell in row):
            continue  # blank row: not worth reporting
        if _TOTAL_ROW.match(name) or (not name and _TOTAL_ROW.match(code)):
            result.skipped_rows.append(offset)
            continue

        if "balance" in columns:
            sides = parse_balance(_cell(row, columns["balance"]))
            if sides is None:
                result.errors.append(f"Row {offset} ({name or code}): the balance is not a number.")
                continue
            debit, credit = sides
        else:
            debit = parse_amount(_cell(row, columns["debit"]))
            credit = parse_amount(_cell(row, columns["credit"]))
            if debit is None or credit is None:
                result.errors.append(f"Row {offset} ({name or code}): an amount is not a number.")
                continue
            if debit < 0:
                debit, credit = 0.0, credit - debit
            if credit < 0:
                debit, credit = debit - credit, 0.0

        if not name and not code:
            if debit or credit:
                result.errors.append(f"Row {offset}: an amount has no account name or code.")
            else:
                result.skipped_rows.append(offset)
            continue

        category_text = _text(_cell(row, columns.get("category"))).lower()
        result.lines.append(
            ImportedLine(
                account_code=code[:40],
                account_name=(name or code)[:200],
                account_group=group[:120],
                debit=round(debit, 2),
                credit=round(credit, 2),
                category=lookup.get(category_text),
                source_ref=f"{where} › row {offset}"[:200],
            )
        )

    if not result.lines and not result.errors:
        result.errors.append("The table has a header but no account rows.")

    # A row named after a group used by other rows is probably that group's
    # subtotal; keeping both would count the same balances twice.
    groups = {line.account_group.lower() for line in result.lines if line.account_group}
    subtotal_rows = [
        line for line in result.lines if line.account_name.lower() in groups
    ]
    if subtotal_rows:
        result.warnings.append(
            "These rows are named like account groups and may be group subtotals, "
            "which would double-count their accounts: "
            + ", ".join(f"{line.account_name} ({line.source_ref.split('› ')[-1]})"
                        for line in subtotal_rows[:5])
            + "."
        )
    return result


def _choose_sheet(sheets: list[SheetImport]) -> str | None:
    usable = [sheet for sheet in sheets if sheet.usable]
    if not usable:
        return None

    def rank(sheet: SheetImport) -> tuple:
        named = "trial" in sheet.name.lower() and "balance" in sheet.name.lower()
        balanced = abs(sheet.total_debit - sheet.total_credit) < 0.005
        return (named, not sheet.errors, balanced, len(sheet.lines))

    return max(usable, key=rank).name


def import_trial_balance_file(
    file_name: str, data: bytes, category_lookup: dict[str, str] | None = None
) -> FileImport:
    """Read every candidate trial balance table in an uploaded file."""
    if len(data) > MAX_FILE_BYTES:
        raise ImportFileError("The file is larger than 5 MB.")
    if not data:
        raise ImportFileError("The file is empty.")

    lower = file_name.lower()
    if lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        workbook, unsaved = _rows_from_xlsx(data)
        sheets = []
        for sheet_name, rows in workbook.items():
            sheet = read_table(rows, sheet_name, file_name, category_lookup)
            if unsaved.get(sheet_name) and sheet.header_row is not None:
                sheet.errors.append(
                    f"{unsaved[sheet_name]} formula cells have no saved result. Open the file "
                    "in Excel, let it calculate, save it, and import it again."
                )
            sheets.append(sheet)
        return FileImport(file_name, "xlsx", sheets, _choose_sheet(sheets))
    if lower.endswith(".xls"):
        raise ImportFileError(
            "Old .xls workbooks are not supported. Save the file as .xlsx or CSV."
        )
    if lower.endswith(".csv") or lower.endswith(".txt") or lower.endswith(".tsv"):
        sheet = read_table(_rows_from_csv(data), "CSV", file_name, category_lookup)
        return FileImport(file_name, "csv", [sheet], sheet.name if sheet.usable else None)
    raise ImportFileError("Import a .xlsx or .csv file.")
