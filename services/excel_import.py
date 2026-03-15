"""Excel import: Alfa-Bank format parser."""
from datetime import datetime
from pathlib import Path


def _parse_amount(val) -> float:
    """Parse amount: -13,31 / 4 015 / -3 470 -> float."""
    if val is None:
        return 0.0
    s = str(val).strip().replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_date(val) -> str | None:
    """Parse DD.MM.YYYY -> YYYY-MM-DD."""
    if val is None or not str(val).strip():
        return None
    s = str(val).strip()
    if s.upper() == "HOLD":
        return None
    try:
        dt = datetime.strptime(s[:10], "%d.%m.%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_alfa_bank(xlsx_path: str | Path) -> list[dict]:
    """
    Parse Alfa-Bank bank statement Excel.
    Returns list of {date, amount, category_bank, description}.
    Skips HOLD, empty dates, zero amounts.
    """
    try:
        import openpyxl
    except ImportError:
        return []

    path = Path(xlsx_path)
    if not path.exists():
        return []

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    if not ws:
        wb.close()
        return []

    result = []
    # Header row 19, data from row 20
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 19:
            continue
        vals = list(row) if row else []
        if len(vals) < 12:
            continue
        date_val = vals[0] if len(vals) > 0 else None
        post_date = vals[1] if len(vals) > 1 else None
        category_bank = str(vals[4]).strip() if len(vals) > 4 and vals[4] else ""
        description = str(vals[10]).strip() if len(vals) > 10 and vals[10] else ""
        amount_raw = vals[11] if len(vals) > 11 else None

        if str(post_date or "").strip().upper() == "HOLD":
            continue
        date_str = _parse_date(date_val) or _parse_date(post_date)
        if not date_str:
            continue
        amount = _parse_amount(amount_raw)
        if amount == 0:
            continue

        result.append({
            "date": date_str,
            "amount": amount,
            "category_bank": category_bank or "Прочее",
            "description": description[:500] if description else "",
        })

    wb.close()
    return result


def get_entry_type_from_amount(amount: float) -> str:
    """Negative -> Expense, positive -> IncomeSecond."""
    return "Expense" if amount < 0 else "IncomeSecond"
