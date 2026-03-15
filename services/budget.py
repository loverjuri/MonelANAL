"""Budget planning and overspend detection."""
from db.repositories import (
    get_budget_limits_map,
    get_expenses_by_category_for_period,
    get_finance_for_period,
)
from services.calculations import get_today_msk


def get_month_range(month_year: str) -> tuple[str, str]:
    """month_year YYYY-MM -> (start_str, end_str)."""
    parts = month_year[:7].split("-")
    if len(parts) < 2:
        return "", ""
    y, m = int(parts[0]), int(parts[1])
    start = f"{y}-{m:02d}-01"
    from datetime import datetime
    if m == 12:
        end_dt = datetime(y + 1, 1, 1)
    else:
        end_dt = datetime(y, m + 1, 1)
    from datetime import timedelta
    end_dt = end_dt - timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%d")
    return start, end


def get_budget_status(session, month_year: str = None) -> dict:
    """
    Returns:
    {
        "month_year": "YYYY-MM",
        "limits": {category: limit},
        "spent": {category: amount},
        "over": [{"category": "...", "limit": X, "spent": Y, "over": Z}],
        "total_limit": X,
        "total_spent": Y,
    }
    """
    if not month_year:
        month_year = get_today_msk()[:7]
    start, end = get_month_range(month_year)
    limits = get_budget_limits_map(session, month_year)
    spent = get_expenses_by_category_for_period(session, start, end)

    over = []
    for cat, limit in limits.items():
        s = spent.get(cat, 0)
        if s > limit:
            over.append({"category": cat, "limit": limit, "spent": s, "over": s - limit})

    return {
        "month_year": month_year,
        "limits": limits,
        "spent": spent,
        "over": over,
        "total_limit": sum(limits.values()),
        "total_spent": sum(spent.values()),
    }


def check_category_overspend(session, category: str, new_amount: float, month_year: str = None) -> dict | None:
    if not month_year:
        month_year = get_today_msk()[:7]
    limits = get_budget_limits_map(session, month_year)
    limit = limits.get(category)
    if limit is None:
        return None
    start, end = get_month_range(month_year)
    spent = get_expenses_by_category_for_period(session, start, end)
    current = spent.get(category, 0)
    total_after = current + new_amount
    if total_after > limit:
        return {
            "category": category,
            "limit": limit,
            "spent": current,
            "after": total_after,
            "over": total_after - limit,
        }
    return None


def suggest_plan_from_history(session, months: int = 3) -> dict:
    """Average expenses per category over last N months. Returns {category: avg_amount}."""
    today = get_today_msk()
    totals = {}
    count = 0
    for offset in range(1, months + 1):
        y = int(today[:4])
        m = int(today[5:7]) - offset
        if m <= 0:
            m += 12
            y -= 1
        my = f"{y}-{m:02d}"
        start, end = get_month_range(my)
        if not start:
            continue
        cats = get_expenses_by_category_for_period(session, start, end)
        for cat, amt in cats.items():
            totals[cat] = totals.get(cat, 0) + amt
        count += 1
    if count == 0:
        return {}
    return {cat: round(total / count) for cat, total in totals.items()}


def get_forecast_end_of_month(session) -> dict:
    """Forecast balance at end of current month."""
    from datetime import datetime
    today = get_today_msk()
    month_year = today[:7]
    start, end = get_month_range(month_year)
    rows = get_finance_for_period(session, start, today)
    income = sum(r.amount for r in rows if r.type in ("IncomeSalary", "IncomeSecond"))
    expense = sum(r.amount for r in rows if r.type == "Expense")
    day_now = int(today[8:10])
    day_end = int(end[8:10])
    days_left = max(day_end - day_now, 0)
    daily_avg = expense / max(day_now, 1)
    projected_expense = expense + daily_avg * days_left
    return {
        "income": income,
        "spent_so_far": expense,
        "daily_avg": round(daily_avg),
        "projected_expense": round(projected_expense),
        "forecast_balance": round(income - projected_expense),
        "days_left": days_left,
    }


def get_5030_20_hint(session) -> str:
    """50/30/20 rule hint based on last month income."""
    today = get_today_msk()
    y, m = int(today[:4]), int(today[5:7])
    prev_m = m - 1 if m > 1 else 12
    prev_y = y if m > 1 else y - 1
    start, end = get_month_range(f"{prev_y}-{prev_m:02d}")
    if not start:
        return "Нет данных за прошлый месяц."
    rows = get_finance_for_period(session, start, end)
    income = sum(r.amount for r in rows if r.type in ("IncomeSalary", "IncomeSecond"))
    if income <= 0:
        return "Нет доходов за прошлый месяц."
    needs = int(income * 0.5)
    wants = int(income * 0.3)
    savings = int(income * 0.2)
    return (
        f"Правило 50/30/20 (доход {int(income)} руб.):\n"
        f"  Необходимое (50%): {needs} руб.\n"
        f"  Желаемое (30%): {wants} руб.\n"
        f"  Накопления (20%): {savings} руб."
    )
