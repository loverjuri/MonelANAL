"""Reports: period-based, comparison, top expenses, daily average."""
from db.repositories import get_finance_for_period, get_expenses_by_category_for_period, get_budget_limits_map
from services.budget import get_month_range
from services.calculations import get_today_msk
from datetime import datetime, timedelta


def get_period_range(period_type: str, ref_date: str = None) -> tuple[str, str]:
    """Get (start, end) for week/month/quarter/year."""
    if not ref_date:
        ref_date = get_today_msk()
    y, m, d = int(ref_date[:4]), int(ref_date[5:7]), int(ref_date[8:10])
    dt = datetime(y, m, d)
    if period_type == "week":
        start = dt - timedelta(days=dt.weekday())
        end = start + timedelta(days=6)
    elif period_type == "month":
        start = datetime(y, m, 1)
        if m == 12:
            end = datetime(y + 1, 1, 1) - timedelta(days=1)
        else:
            end = datetime(y, m + 1, 1) - timedelta(days=1)
    elif period_type == "quarter":
        q_start_month = ((m - 1) // 3) * 3 + 1
        start = datetime(y, q_start_month, 1)
        q_end_month = q_start_month + 2
        if q_end_month == 12:
            end = datetime(y + 1, 1, 1) - timedelta(days=1)
        else:
            end = datetime(y, q_end_month + 1, 1) - timedelta(days=1)
    elif period_type == "year":
        start = datetime(y, 1, 1)
        end = datetime(y, 12, 31)
    else:
        return get_month_range(ref_date[:7])
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def generate_period_report(session, period_type: str, ref_date: str = None) -> str:
    start, end = get_period_range(period_type, ref_date)
    rows = get_finance_for_period(session, start, end)
    income = expense = 0
    by_cat = {}
    for r in rows:
        if getattr(r, "exclude_from_budget", False) and r.type == "Expense":
            continue
        amt = r.amount or 0
        if r.type in ("IncomeSalary", "IncomeSecond"):
            income += amt
        elif r.type == "Expense":
            expense += amt
            by_cat[r.category or "Без категории"] = by_cat.get(r.category or "Без категории", 0) + amt
    period_names = {"week": "неделю", "month": "месяц", "quarter": "квартал", "year": "год"}
    lines = [
        f"Отчёт за {period_names.get(period_type, period_type)} ({start} — {end})",
        f"Доходы: {int(income)} руб.",
        f"Расходы: {int(expense)} руб.",
        f"Баланс: {int(income - expense)} руб.",
        "", "По категориям:",
    ]
    for cat in sorted(by_cat.keys(), key=lambda c: -by_cat[c]):
        lines.append(f"  {cat}: {int(by_cat[cat])} руб.")
    return "\n".join(lines)


def compare_with_previous(session, period_type: str) -> str:
    today = get_today_msk()
    cur_start, cur_end = get_period_range(period_type, today)
    y, m, d = int(today[:4]), int(today[5:7]), int(today[8:10])
    if period_type == "month":
        prev_m = m - 1 if m > 1 else 12
        prev_y = y if m > 1 else y - 1
        prev_ref = f"{prev_y}-{prev_m:02d}-01"
    elif period_type == "week":
        prev_ref = (datetime(y, m, d) - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period_type == "quarter":
        prev_ref = (datetime(y, m, d) - timedelta(days=90)).strftime("%Y-%m-%d")
    else:
        prev_ref = f"{y-1}-{m:02d}-{d:02d}"
    prev_start, prev_end = get_period_range(period_type, prev_ref)
    cur_cats = get_expenses_by_category_for_period(session, cur_start, cur_end)
    prev_cats = get_expenses_by_category_for_period(session, prev_start, prev_end)
    all_cats = set(list(cur_cats.keys()) + list(prev_cats.keys()))
    lines = [f"Сравнение: {cur_start[:7]} vs {prev_start[:7]}"]
    cur_total = sum(cur_cats.values())
    prev_total = sum(prev_cats.values())
    delta = cur_total - prev_total
    sign = "+" if delta >= 0 else ""
    lines.append(f"Итого: {int(cur_total)} vs {int(prev_total)} ({sign}{int(delta)})")
    lines.append("")
    for cat in sorted(all_cats):
        c = cur_cats.get(cat, 0)
        p = prev_cats.get(cat, 0)
        d = c - p
        s = "+" if d >= 0 else ""
        if c or p:
            lines.append(f"  {cat}: {int(c)} vs {int(p)} ({s}{int(d)})")
    return "\n".join(lines)


def get_top_expenses(session, start: str, end: str, limit: int = 5) -> list:
    rows = get_finance_for_period(session, start, end)
    expenses = [r for r in rows if r.type == "Expense" and not getattr(r, "exclude_from_budget", False)]
    expenses.sort(key=lambda r: r.amount or 0, reverse=True)
    return expenses[:limit]


def get_daily_average(session, start: str, end: str) -> float:
    rows = get_finance_for_period(session, start, end)
    total = sum(r.amount for r in rows if r.type == "Expense" and not getattr(r, "exclude_from_budget", False))
    try:
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
        days = max((e - s).days + 1, 1)
    except Exception:
        days = 30
    return total / days
