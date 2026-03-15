"""Goal management: auto-fund, pace hints, cushion calculation."""
from datetime import datetime, timedelta
from db.models import Goal, get_session
from db.repositories import get_active_goals, update_goal_current, get_expenses_by_category_for_period

GOAL_TYPE_ICONS = {
    "vacation": "✈️", "tech": "💻", "cushion": "🛡️",
    "purchase": "🛒", "other": "🎯",
}


def get_goal_icon(goal_type: str) -> str:
    return GOAL_TYPE_ICONS.get(goal_type, "🎯")


def process_auto_fund(session, received_amount: float) -> list:
    """Auto-fund goals from payday. Returns list of funded goals info."""
    goals = session.query(Goal).filter_by(is_active=True).all()
    funded = []
    for g in goals:
        if getattr(g, "is_archived", False):
            continue
        amount = 0
        auto_percent = getattr(g, "auto_fund_percent", None)
        auto_amount = getattr(g, "auto_fund_amount", None)
        if auto_percent and auto_percent > 0:
            amount = received_amount * auto_percent / 100
        elif auto_amount and auto_amount > 0:
            amount = auto_amount
        if amount > 0:
            remaining = g.target_amount - (g.current_amount or 0)
            amount = min(amount, remaining) if remaining > 0 else 0
            if amount > 0:
                g.current_amount = (g.current_amount or 0) + amount
                funded.append({"name": g.name, "amount": amount, "current": g.current_amount, "target": g.target_amount})
    if funded:
        session.commit()
    return funded


def get_goal_pace_hint(goal) -> str:
    """'At current pace, X months remaining'."""
    if not goal.current_amount or goal.current_amount <= 0:
        return "Ещё нет пополнений"
    if goal.current_amount >= goal.target_amount:
        return "Цель достигнута!"
    remaining = goal.target_amount - goal.current_amount
    if goal.created_at:
        days_elapsed = max((datetime.utcnow() - goal.created_at).days, 1)
        rate_per_day = goal.current_amount / days_elapsed
        if rate_per_day > 0:
            days_left = int(remaining / rate_per_day)
            months = days_left // 30
            return f"При текущем темпе: ~{months} мес. ({days_left} дн.)"
    return "Недостаточно данных"


def get_cushion_target(session) -> float:
    """3-6 monthly expenses as safety cushion target."""
    from services.budget import get_month_range
    from services.calculations import get_today_msk
    today = get_today_msk()
    total = 0
    count = 0
    for m_offset in range(1, 4):
        y = int(today[:4])
        mo = int(today[5:7]) - m_offset
        if mo <= 0:
            mo += 12
            y -= 1
        my = f"{y}-{mo:02d}"
        start, end = get_month_range(my)
        if start:
            expenses = get_expenses_by_category_for_period(session, start, end)
            month_total = sum(expenses.values())
            if month_total > 0:
                total += month_total
                count += 1
    avg = total / count if count > 0 else 30000
    return avg * 4.5  # middle of 3-6 range
