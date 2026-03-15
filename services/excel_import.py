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


def _looks_like_amount(val) -> bool:
    """True if val looks like a number (e.g. -13,31 or 4 015)."""
    if val is None or not str(val).strip():
        return False
    s = str(val).strip().replace(" ", "").replace(",", ".")
    if s.startswith("-") or s.startswith("+"):
        s = s[1:]
    return s.replace(".", "", 1).isdigit()


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
    # Alfa-Bank format: 0=date, 1=post_date, 4=category, 10/11=description, 11/12=amount
    # Newer exports: description at 11, amount at 12
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 19:
            continue
        vals = list(row) if row else []
        if len(vals) < 12:
            continue
        date_val = vals[0] if len(vals) > 0 else None
        post_date = vals[1] if len(vals) > 1 else None
        category_bank = str(vals[4]).strip() if len(vals) > 4 and vals[4] else ""
        # Newer Alfa format: description at 11, amount at 12
        # Older format: description at 10, amount at 11
        desc_10 = str(vals[10]).strip() if len(vals) > 10 and vals[10] else ""
        desc_11 = str(vals[11]).strip() if len(vals) > 11 and vals[11] else ""
        if _looks_like_amount(desc_11):
            description = desc_10
            amount_raw = vals[11]
        else:
            description = desc_11
            amount_raw = vals[12] if len(vals) > 12 else vals[11]

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
