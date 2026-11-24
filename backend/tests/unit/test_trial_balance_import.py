"""Tests for reading trial balances from CSV and Excel exports."""

import io

import openpyxl
import pytest

from app.services.trial_balance_import import (
    ImportFileError,
    import_trial_balance_file,
    parse_amount,
    parse_balance,
)
from tests.fixtures.tally_reference import TALLY_TRIAL_BALANCE


def _xlsx(sheets: dict[str, list[list]]) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "text,value",
    [("1,250.00", 1250), ("MYR 300", 300), ("₹ 12", 12), ("(10,000)", -10000),
     ("-5", -5), ("", 0), ("-", 0), (None, 0), (42, 42), ("abc1x", None)],
)
def test_parse_amount(text, value):
    assert parse_amount(text) == value


@pytest.mark.parametrize(
    "text,sides",
    [("1,000.00 Dr", (1000, 0)), ("1,000.00 Cr", (0, 1000)), ("250", (250, 0)),
     ("-250", (0, 250)), (-75.5, (0, 75.5)), ("x", None)],
)
def test_parse_balance(text, sides):
    assert parse_balance(text) == sides


def test_csv_with_report_titles_and_total_row():
    csv = (
        "CrystalCorps Sdn Bhd\nTrial Balance as at 31/12/2025\n\n"
        "N/C,Name,Debit,Credit\n"
        '1200,Bank Current Account,"5,000.00",\n'
        '3000,Share capital,,"5,000.00"\n'
        ',Totals:,"5,000.00","5,000.00"\n'
    ).encode()
    result = import_trial_balance_file("tb.csv", csv)
    sheet = result.sheets[0]
    assert result.selected_sheet == "CSV"
    assert sheet.header_row == 4
    assert sheet.skipped_rows == [7]
    assert [(l.account_code, l.account_name, l.debit, l.credit) for l in sheet.lines] == [
        ("1200", "Bank Current Account", 5000, 0),
        ("3000", "Share capital", 0, 5000),
    ]
    assert sheet.lines[0].source_ref == "tb.csv › row 5"


def test_semicolon_csv_and_negative_amounts_move_side():
    csv = "Account;Dr;Cr\nOverdrawn bank;(200);\nCapital;;-50\n".encode()
    lines = import_trial_balance_file("tb.csv", csv).sheets[0].lines
    assert (lines[0].debit, lines[0].credit) == (0, 200)
    assert (lines[1].debit, lines[1].credit) == (50, 0)


def test_single_balance_column_with_dr_cr_markers():
    csv = "Particulars,Group,Closing Balance\nCash,Cash-in-Hand,500.00 Dr\nCapital,Capital,500.00 Cr\n"
    lines = import_trial_balance_file("tally.csv", csv.encode()).sheets[0].lines
    assert [(l.account_name, l.account_group, l.debit, l.credit) for l in lines] == [
        ("Cash", "Cash-in-Hand", 500, 0),
        ("Capital", "Capital", 0, 500),
    ]


def test_category_column_is_read_by_code_or_label():
    csv = "Account name,Debit,Credit,Category\nPetty cash,10,,Cash and bank\nCapital,,10,equity\n"
    lookup = {"cash and bank": "cash", "cash": "cash", "equity": "equity"}
    lines = import_trial_balance_file("tb.csv", csv.encode(), lookup).sheets[0].lines
    assert [line.category for line in lines] == ["cash", "equity"]


def test_amount_that_is_not_a_number_is_an_error():
    sheet = import_trial_balance_file("tb.csv", b"Name,Debit,Credit\nCash,abc1x,\n").sheets[0]
    assert sheet.errors and "not a number" in sheet.errors[0]
    assert sheet.lines == []


def test_amount_without_an_account_is_an_error():
    sheet = import_trial_balance_file("tb.csv", b"Name,Debit,Credit\n,100,\nCash,,100\n").sheets[0]
    assert any("no account name" in error for error in sheet.errors)


def test_file_without_a_trial_balance_table():
    sheet = import_trial_balance_file("x.csv", b"Date,Voucher No,Amount\n1,2,3\n").sheets[0]
    assert sheet.header_row is None
    assert "No header row" in sheet.errors[0]


def test_workbook_picks_the_trial_balance_sheet_among_others():
    rows = [["Ledger", "Group", "Debit", "Credit"]] + [list(r) for r in TALLY_TRIAL_BALANCE]
    rows.append(["Totals", None, 6258631.34, 6258631.34])
    data = _xlsx({
        "Inputs": [["Metric", "Value"], ["Net Sales", 1]],
        "Ledgers": [["Ledger Name", "Group", "Opening Balance"], ["Cash", "Cash-in-Hand", 5]],
        "Trial Balance": rows,
        "Receipts": [["Date", "Voucher No", "Party Ledger", "Amount"], ["01-Apr", "R1", "C", 5]],
    })
    result = import_trial_balance_file("statements.xlsx", data)
    assert result.selected_sheet == "Trial Balance"
    sheet = next(s for s in result.sheets if s.name == "Trial Balance")
    assert len(sheet.lines) == 17
    assert sheet.skipped_rows == [19]
    assert sheet.total_debit == sheet.total_credit == pytest.approx(6258631.34)
    assert sheet.lines[3].account_group == "Duties & Taxes"
    assert sheet.lines[0].source_ref == "statements.xlsx › Trial Balance › row 2"
    # Sheets without a trial balance table are reported, not imported.
    ledgers = next(s for s in result.sheets if s.name == "Ledgers")
    assert ledgers.header_row is None and ledgers.lines == []


def test_formulas_without_saved_results_are_reported():
    # openpyxl writes formulas without results, as a never-opened file would be.
    data = _xlsx({"TB": [["Account", "Debit", "Credit"], ["Cash", "=5+5", None],
                         ["Capital", None, 10]]})
    sheet = import_trial_balance_file("tb.xlsx", data).sheets[0]
    assert any("formula cells have no saved result" in error for error in sheet.errors)


def test_group_subtotal_rows_are_flagged():
    csv = ("Account,Group,Debit,Credit\nCash,Current Assets,10,\nDebtors,Current Assets,5,\n"
           "Current Assets,,15,\nCapital,Capital,,30\n")
    sheet = import_trial_balance_file("tb.csv", csv.encode()).sheets[0]
    assert any("group subtotals" in warning for warning in sheet.warnings)


@pytest.mark.parametrize(
    "name,data,message",
    [("tb.xls", b"x", "Old .xls"), ("tb.pdf", b"x", ".xlsx or .csv"), ("tb.csv", b"", "empty"),
     ("tb.xlsx", b"not a zip", "could not be read")],
)
def test_unreadable_files_are_refused(name, data, message):
    with pytest.raises(ImportFileError, match=message):
        import_trial_balance_file(name, data)


def test_large_files_are_refused():
    with pytest.raises(ImportFileError, match="5 MB"):
        import_trial_balance_file("tb.csv", b"x" * (5 * 1024 * 1024 + 1))
