"""Gamification: achievements, streaks."""
from datetime import datetime, timedelta
from db.repositories import get_finance_for_period, get_session
from services.calculations import get_today_msk


ACHIEVEMENTS = {
    "first_expense": {"name": "Первый расход", "desc": "Записал первый расход"},
    "week_no_overspend": {"name": "Неделя без перерасхода", "desc": "7 дней без превышения лимитов"},
    "goal_reached": {"name": "Цель достигнута", "desc": "Достиг финансовой цели"},
    "streak_7": {"name": "Неделя подряд", "desc": "7 дней подряд ведёте учёт"},
    "streak_30": {"name": "Месяц подряд", "desc": "30 дней подряд ведёте учёт"},
    "saver_10": {"name": "Экономист", "desc": "Сэкономили 10% от бюджета"},
}


def get_streak(session) -> int:
    """Days in a row with at least one finance entry."""
    today = get_today_msk()
    streak = 0
    dt = datetime.strptime(today, "%Y-%m-%d")
    for i in range(365):
        d = (dt - timedelta(days=i)).strftime("%Y-%m-%d")
        rows = get_finance_for_period(session, d, d)
        if rows:
            streak += 1
        else:
            break
    return streak


def check_achievements(session) -> list[str]:
    """Check and return newly unlocked achievement codes."""
    from db.models import Achievement
    unlocked = {a.code for a in session.query(Achievement).all()}
    new = []
    if "first_expense" not in unlocked:
        rows = get_finance_for_period(session, "2000-01-01", "2099-12-31")
        if any(r.type == "Expense" for r in rows):
            new.append("first_expense")
    streak = get_streak(session)
    if streak >= 7 and "streak_7" not in unlocked:
        new.append("streak_7")
    if streak >= 30 and "streak_30" not in unlocked:
        new.append("streak_30")
    for code in new:
        session.add(Achievement(code=code, name=ACHIEVEMENTS[code]["name"], description=ACHIEVEMENTS[code]["desc"]))
    if new:
        session.commit()
    return new


def get_unlocked(session) -> list:
    from db.models import Achievement
    return session.query(Achievement).all()


def format_achievements(session) -> str:
    unlocked = get_unlocked(session)
    streak = get_streak(session)
    lines = [f"Streak: {streak} дн. подряд", ""]
    if unlocked:
        lines.append("Достижения:")
        for a in unlocked:
            lines.append(f"  🏆 {a.name} — {a.description}")
    else:
        lines.append("Достижений пока нет.")
    return "\n".join(lines)
