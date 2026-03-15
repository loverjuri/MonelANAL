"""Backup: export data and send as file."""
import json
import tempfile
import os
from db.repositories import get_session
from services.calculations import get_today_msk


def create_backup_json(session) -> str:
    """Create full backup JSON file. Returns path."""
    from db.models import Config, WorkLog, Order, Finance, BudgetPlan, Goal, Subscription, Calculation, Debt, DebtPayment
    data = {
        "backup_date": get_today_msk(),
        "config": {r.parameter: r.value for r in session.query(Config).all()},
        "worklog": [{"id": r.id, "date": r.date, "job_type": r.job_type, "hours": r.hours_worked, "status": r.status} for r in session.query(WorkLog).all()],
        "orders": [{"id": r.order_id, "date": r.date, "desc": r.description, "amount": r.amount} for r in session.query(Order).all()],
        "finance": [{"id": r.id, "date": r.date, "type": r.type, "amount": r.amount, "category": r.category, "comment": r.comment} for r in session.query(Finance).all()],
        "budget": [{"month": r.month_year, "cat": r.category, "limit": r.limit_amount} for r in session.query(BudgetPlan).all()],
        "goals": [{"id": r.id, "name": r.name, "target": r.target_amount, "current": r.current_amount} for r in session.query(Goal).all()],
        "subscriptions": [{"id": r.id, "name": r.name, "amount": r.amount, "cycle": r.cycle} for r in session.query(Subscription).all()],
        "debts": [{"id": r.id, "direction": r.direction, "counterparty": r.counterparty, "remaining": r.remaining_amount} for r in session.query(Debt).all()],
    }
    fd, path = tempfile.mkstemp(suffix=".json", prefix="backup_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, ensure_ascii=False, indent=2, fp=f)
    return path


def delete_all_data(session):
    """Delete all user data from all tables."""
    from db.models import WorkLog, Order, Finance, BudgetPlan, Goal, Subscription, Calculation, Debt, DebtPayment, State, Log, Achievement, ExpenseTemplate
    for model in [Finance, WorkLog, Order, BudgetPlan, Goal, Subscription, Calculation, Debt, DebtPayment, State, Log, Achievement, ExpenseTemplate]:
        try:
            session.query(model).delete()
        except Exception:
            pass
    session.commit()


def cleanup_old_logs(session, days: int = 30):
    """Delete logs older than N days."""
    from datetime import datetime, timedelta
    from db.models import Log
    cutoff = datetime.utcnow() - timedelta(days=days)
    session.query(Log).filter(Log.timestamp < cutoff).delete()
    session.commit()
