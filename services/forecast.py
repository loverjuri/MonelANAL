"""Cash flow forecast for 1-3 months."""
from datetime import datetime, timedelta
from db.repositories import (
    get_finance_for_period, get_active_subscriptions,
    get_expenses_by_category_for_period,
)
from services.budget import get_month_range
from services.calculations import get_today_msk


def get_average_monthly_income(session, months: int = 3) -> float:
    today = get_today_msk()
    total = 0
    count = 0
    for offset in range(1, months + 1):
        y = int(today[:4])
        m = int(today[5:7]) - offset
        if m <= 0:
            m += 12
            y -= 1
        start, end = get_month_range(f"{y}-{m:02d}")
        if not start:
            continue
        rows = get_finance_for_period(session, start, end)
        inc = sum(r.amount for r in rows if r.type in ("IncomeSalary", "IncomeSecond"))
        if inc > 0:
            total += inc
            count += 1
    return total / count if count > 0 else 0


def get_average_monthly_expense(session, months: int = 3) -> float:
    today = get_today_msk()
    total = 0
    count = 0
    for offset in range(1, months + 1):
        y = int(today[:4])
        m = int(today[5:7]) - offset
        if m <= 0:
            m += 12
            y -= 1
        start, end = get_month_range(f"{y}-{m:02d}")
        if not start:
            continue
        rows = get_finance_for_period(session, start, end)
        exp = sum(r.amount for r in rows if r.type == "Expense")
        if exp > 0:
            total += exp
            count += 1
    return total / count if count > 0 else 0


def get_recurring_monthly(session) -> float:
    """Total monthly recurring subscriptions."""
    subs = get_active_subscriptions(session)
    total = 0
    for s in subs:
        if s.cycle == "monthly":
            total += s.amount
        elif s.cycle == "weekly":
            total += s.amount * 4.33
        elif s.cycle == "yearly":
            total += s.amount / 12
    return total


def forecast_cash_flow(session, months: int = 3) -> list[dict]:
    """Returns list of {month, income, expense, net, balance} for next N months."""
    avg_income = get_average_monthly_income(session)
    avg_expense = get_average_monthly_expense(session)
    recurring = get_recurring_monthly(session)
    today = get_today_msk()
    y, m = int(today[:4]), int(today[5:7])
    
    from services.calculations import get_budget_balance
    balance = get_budget_balance(session)
    
    result = []
    for i in range(1, months + 1):
        nm = m + i
        ny = y
        while nm > 12:
            nm -= 12
            ny += 1
        month_label = f"{ny}-{nm:02d}"
        projected_expense = max(avg_expense, recurring)
        net = avg_income - projected_expense
        balance += net
        result.append({
            "month": month_label,
            "income": int(avg_income),
            "expense": int(projected_expense),
            "net": int(net),
            "balance": int(balance),
        })
    return result
