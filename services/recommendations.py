"""Recommendations engine: overspend, averages, seasonal, AI."""
from db.repositories import (
    get_config_param, get_expenses_by_category_for_period,
    get_finance_for_period, get_session,
)
from services.calculations import get_today_msk
from services.budget import get_month_range, get_budget_status


def check_large_expense(session, amount: float) -> bool:
    """Returns True if amount exceeds LargeExpenseThreshold."""
    threshold = get_config_param(session, "LargeExpenseThreshold")
    t = float(threshold) if threshold else 10000
    return amount >= t


def get_category_vs_average(session, category: str, months: int = 3) -> dict | None:
    """Compare current month category spend vs N-month average."""
    today = get_today_msk()
    cur_start, cur_end = get_month_range(today[:7])
    cur_expenses = get_expenses_by_category_for_period(session, cur_start, cur_end)
    current = cur_expenses.get(category, 0)

    totals = []
    for m_offset in range(1, months + 1):
        y = int(today[:4])
        mo = int(today[5:7]) - m_offset
        if mo <= 0:
            mo += 12
            y -= 1
        my = f"{y}-{mo:02d}"
        start, end = get_month_range(my)
        if start:
            expenses = get_expenses_by_category_for_period(session, start, end)
            totals.append(expenses.get(category, 0))
    if not totals:
        return None
    avg = sum(totals) / len(totals)
    if avg <= 0:
        return None
    pct_change = ((current - avg) / avg) * 100
    if abs(pct_change) < 10:
        return None
    return {"category": category, "current": current, "average": avg, "pct_change": pct_change}


def get_seasonal_comparison(session, category: str) -> dict | None:
    """Compare this month vs same month last year."""
    today = get_today_msk()
    y = int(today[:4])
    m = int(today[5:7])
    cur_start, cur_end = get_month_range(f"{y}-{m:02d}")
    prev_start, prev_end = get_month_range(f"{y-1}-{m:02d}")
    cur = get_expenses_by_category_for_period(session, cur_start, cur_end).get(category, 0)
    prev = get_expenses_by_category_for_period(session, prev_start, prev_end).get(category, 0)
    if prev <= 0:
        return None
    pct = ((cur - prev) / prev) * 100
    return {"category": category, "current": cur, "last_year": prev, "pct_change": pct}


def get_template_advice(session) -> list[str]:
    """Generate rule-based advice."""
    advice = []
    st = get_budget_status(session)
    for o in st.get("over", []):
        cat = o["category"]
        over = int(o["over"])
        advice.append(f"Сократите {cat}: перерасход {over} руб.")
    if st["total_spent"] > 0 and st["total_limit"] > 0:
        pct = st["total_spent"] / st["total_limit"] * 100
        if pct > 80:
            advice.append(f"Потрачено {int(pct)}% от общего бюджета — осторожнее!")
    return advice


def generate_daily_digest(session) -> str:
    """Full daily digest with recommendations."""
    lines = []
    st = get_budget_status(session)
    over_items = st.get("over", [])
    if over_items:
        lines.append("⚠ Перерасход:")
        for o in over_items:
            lines.append(f"  {o['category']}: +{int(o['over'])} руб.")
    advice = get_template_advice(session)
    if advice:
        lines.append("")
        lines.append("Советы:")
        for a in advice:
            lines.append(f"  • {a}")
    from services.goals import get_goal_icon, get_goal_pace_hint
    from db.repositories import get_active_goals
    goals = get_active_goals(session)
    if goals:
        lines.append("")
        lines.append("Цели:")
        for g in goals:
            icon = get_goal_icon(getattr(g, "goal_type", None) or "other")
            pct = int(100 * (g.current_amount or 0) / g.target_amount) if g.target_amount else 0
            hint = get_goal_pace_hint(g)
            lines.append(f"  {icon} {g.name}: {pct}% — {hint}")
    return "\n".join(lines) if lines else ""
