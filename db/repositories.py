"""Database repositories for CRUD operations."""
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from db.models import (
    Base, engine, SessionLocal, get_session, generate_id,
    Config, WorkLog, Order, Finance, State, Log, Calculation,
    BudgetPlan, Goal, Subscription,
    Debt, DebtPayment, Category, Tag, ExpenseTemplate, Achievement,
    AuditLog, User,
)

TZ = ZoneInfo("Europe/Moscow")


def format_date_for_compare(d) -> str:
    if isinstance(d, str):
        return d[:10] if len(d) >= 10 else d
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def get_today_msk() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def get_yesterday_msk() -> str:
    from datetime import timedelta
    return (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")


# Config
def get_config_map(session: Session) -> dict:
    rows = session.query(Config).all()
    return {r.parameter: r.value for r in rows if r.parameter}


def get_config_param(session: Session, name: str) -> Optional[str]:
    r = session.query(Config).filter(Config.parameter == name).first()
    return r.value if r else None


def set_config_param(session: Session, name: str, value: str):
    r = session.query(Config).filter(Config.parameter == name).first()
    if r:
        r.value = value
    else:
        session.add(Config(parameter=name, value=value))
    session.commit()


# User (web auth)
def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.query(User).filter(User.username == username).first()


def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    return session.query(User).filter(User.id == user_id).first()


def update_user(session: Session, user_id: int, **kwargs) -> bool:
    u = get_user_by_id(session, user_id)
    if not u:
        return False
    for k, v in kwargs.items():
        if hasattr(u, k):
            setattr(u, k, v)
    session.commit()
    return True


# WorkLog
def get_next_sick_day_index(session: Session, date_str: str) -> int:
    """For sick leave: if previous day was sick, return prev_index+1, else 1."""
    from datetime import datetime, timedelta
    try:
        parts = date_str[:10].split("-")
        if len(parts) < 3:
            return 1
        current_dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
        prev_date = (current_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    except (ValueError, IndexError):
        return 1
    rows = (
        session.query(WorkLog)
        .filter(WorkLog.job_type == "Main", WorkLog.status == "Sick")
        .order_by(WorkLog.date.desc())
        .all()
    )
    for r in rows:
        row_date = r.date[:10] if r.date else ""
        if row_date == prev_date:
            prev_index = r.sick_day_index or 1
            return prev_index + 1
        break  # We only check immediate previous
    return 1


def add_work_log(
    session: Session,
    date_str: str,
    job_type: str,
    hours_worked: float,
    status: str,
    hour_rate: float,
    sick_day_index: Optional[int] = None,
    is_paid: bool = True,
) -> str:
    sid = None
    paid = is_paid
    if status == "Sick":
        sid = get_next_sick_day_index(session, date_str)
        paid = sid <= 3
    rid = generate_id()
    session.add(WorkLog(
        id=rid,
        date=date_str[:10],
        job_type=job_type,
        hours_worked=hours_worked,
        hour_rate_snapshot=hour_rate,
        status=status,
        sick_day_index=sid,
        is_paid=paid,
    ))
    session.commit()
    return rid


def get_work_log_for_period(session: Session, start_str: str, end_str: str, job_type: Optional[str] = None):
    q = session.query(WorkLog).filter(
        WorkLog.date >= start_str,
        WorkLog.date <= end_str,
    )
    if job_type:
        q = q.filter(WorkLog.job_type == job_type)
    return q.all()


def has_work_log_for_date(session: Session, date_str: str, job_type: Optional[str] = None) -> bool:
    date_norm = date_str[:10] if len(date_str) >= 10 else date_str
    q = session.query(WorkLog).filter(WorkLog.date == date_norm)
    if job_type:
        q = q.filter(WorkLog.job_type == job_type)
    return q.first() is not None


def get_work_log(session: Session, wl_id: str):
    return session.query(WorkLog).filter(WorkLog.id == wl_id).first()


def update_work_log(session: Session, wl_id: str, **kwargs) -> bool:
    w = get_work_log(session, wl_id)
    if not w:
        return False
    for k, v in kwargs.items():
        if hasattr(w, k):
            if k == "date" and v:
                setattr(w, k, v[:10])
            else:
                setattr(w, k, v)
    session.commit()
    return True


# Orders
def add_order(session: Session, date_str: str, description: str, amount: float, status: str = "New") -> str:
    oid = generate_id()
    session.add(Order(
        order_id=oid,
        date=date_str[:10],
        description=description,
        amount=amount,
        status=status,
    ))
    session.commit()
    return oid


def add_order_with_items(session: Session, date_str: str, items: list) -> Optional[str]:
    if not items:
        return None
    total = 0
    desc_parts = []
    for it in items:
        amt = float(it.get("amount", 0) or 0)
        total += amt
        desc_parts.append(f"{str(it.get('description', '')).strip()} — {amt}")
    return add_order(session, date_str[:10], "; ".join(desc_parts), total)


def get_order(session: Session, order_id: str):
    return session.query(Order).filter(Order.order_id == order_id).first()


def update_order(session: Session, order_id: str, **kwargs) -> bool:
    o = get_order(session, order_id)
    if not o:
        return False
    for k, v in kwargs.items():
        if hasattr(o, k):
            if k == "date" and v:
                setattr(o, k, v[:10])
            else:
                setattr(o, k, v)
    session.commit()
    return True


def delete_order(session: Session, order_id: str) -> bool:
    o = get_order(session, order_id)
    if not o:
        return False
    session.delete(o)
    session.commit()
    return True


def get_orders_for_period(session: Session, start_str: str, end_str: str):
    return session.query(Order).filter(
        Order.date >= start_str,
        Order.date <= end_str,
    ).all()


def sum_orders_for_period(session: Session, start_str: str, end_str: str) -> float:
    orders = get_orders_for_period(session, start_str, end_str)
    return sum(o.amount for o in orders)


def has_orders_for_date(session: Session, date_str: str) -> bool:
    date_norm = date_str[:10] if len(date_str) >= 10 else date_str
    return session.query(Order).filter(Order.date == date_norm).first() is not None


# Finance
def add_finance_entry(
    session: Session,
    date_str: str,
    entry_type: str,
    amount: float,
    category: str = "",
    comment: str = "",
    exclude_from_budget: bool = False,
) -> str:
    rid = generate_id()
    session.add(Finance(
        id=rid,
        date=date_str[:10],
        type=entry_type,
        amount=amount,
        category=category or "",
        comment=comment or "",
        exclude_from_budget=exclude_from_budget,
    ))
    session.commit()
    return rid


def get_finance_for_period(session: Session, start_str: str, end_str: str, include_deleted: bool = False):
    q = session.query(Finance).filter(
        Finance.date >= start_str,
        Finance.date <= end_str,
    )
    if not include_deleted:
        q = q.filter(Finance.is_deleted == False)
    return q.all()


def record_payday_received(
    session: Session,
    date_str: str,
    amount_received: float,
    accrued_main: float,
    accrued_second: float,
    period_start: str,
    period_end: str,
):
    add_finance_entry(session, date_str[:10], "IncomeSalary", amount_received, "ЗП Выплата", "Фактически получено")
    total_accrued = (accrued_main or 0) + (accrued_second or 0)
    diff = total_accrued - amount_received
    if abs(diff) > 0.01:
        add_finance_entry(session, date_str[:10], "Correction", -diff, "Корректировка", "Разница начислено/получено")
    session.add(Calculation(
        period_start=period_start,
        period_end=period_end,
        accrued_salary=total_accrued,
        received_salary=amount_received,
        difference=-diff,
    ))
    session.commit()


# State
def get_state(session: Session, chat_id) -> Optional[dict]:
    import json
    r = session.query(State).filter(State.chat_id == str(chat_id)).first()
    if not r:
        return None
    payload = {}
    if r.payload:
        try:
            payload = json.loads(r.payload)
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "scenario": r.scenario,
        "step": r.step,
        "payload": payload,
        "updatedAt": r.updated_at,
    }


def set_state(session: Session, chat_id, scenario: str, step: str, payload: dict):
    import json
    payload_str = json.dumps(payload) if payload else "{}"
    r = session.query(State).filter(State.chat_id == str(chat_id)).first()
    if r:
        r.scenario = scenario
        r.step = step
        r.payload = payload_str
        r.updated_at = datetime.utcnow()
    else:
        session.add(State(chat_id=str(chat_id), scenario=scenario, step=step, payload=payload_str))
    session.commit()


def clear_state(session: Session, chat_id):
    session.query(State).filter(State.chat_id == str(chat_id)).delete()
    session.commit()


# Logs (resilient: if logs table missing, rollback and continue)
def log_info(session: Session, message: str):
    try:
        session.add(Log(level="Info", message=message))
        session.commit()
    except Exception:
        session.rollback()


def log_error(session: Session, message: str):
    try:
        session.add(Log(level="Error", message=message))
        session.commit()
    except Exception:
        session.rollback()


def log_error_with_exception(session: Session, context: str, err: Exception):
    msg = f"{context}: {getattr(err, 'message', str(err))}"
    log_error(session, msg)


# BudgetPlan
def get_budget_plan_for_month(session: Session, month_year: str) -> list:
    """month_year: YYYY-MM"""
    return session.query(BudgetPlan).filter(
        BudgetPlan.month_year == month_year[:7]
    ).all()


def set_budget_plan_limit(session: Session, month_year: str, category: str, limit_amount: float) -> str:
    """Set or update budget limit for category. Returns id."""
    existing = session.query(BudgetPlan).filter(
        BudgetPlan.month_year == month_year[:7],
        BudgetPlan.category == category,
    ).first()
    if existing:
        existing.limit_amount = limit_amount
        session.commit()
        return existing.id
    rid = generate_id()
    session.add(BudgetPlan(
        id=rid,
        month_year=month_year[:7],
        category=category,
        limit_amount=limit_amount,
    ))
    session.commit()
    return rid


def get_budget_limits_map(session: Session, month_year: str) -> dict:
    """Returns {category: limit_amount}."""
    rows = get_budget_plan_for_month(session, month_year)
    return {r.category: r.limit_amount for r in rows}


# Goal
def get_active_goals(session: Session) -> list:
    return session.query(Goal).filter(Goal.is_active == True).order_by(Goal.priority.desc(), Goal.deadline).all()


def add_goal(session: Session, name: str, target_amount: float, deadline: str = None, priority: int = 0) -> str:
    rid = generate_id()
    session.add(Goal(
        id=rid, name=name, target_amount=target_amount, current_amount=0,
        deadline=deadline or "", priority=priority,
    ))
    session.commit()
    return rid


def update_goal_current(session: Session, goal_id: str, add_amount: float) -> bool:
    g = session.query(Goal).filter(Goal.id == goal_id).first()
    if not g:
        return False
    g.current_amount = (g.current_amount or 0) + add_amount
    session.commit()
    return True


def update_goal(session: Session, goal_id: str, **kwargs) -> bool:
    g = session.query(Goal).filter(Goal.id == goal_id).first()
    if not g:
        return False
    for k, v in kwargs.items():
        if hasattr(g, k):
            if k in ("deadline",) and v is not None:
                setattr(g, k, v[:10] if v else "")
            else:
                setattr(g, k, v)
    session.commit()
    return True


def get_goal(session: Session, goal_id: str):
    return session.query(Goal).filter(Goal.id == goal_id).first()


def transfer_between_goals(session: Session, from_goal_id: str, to_goal_id: str, amount: float) -> bool:
    """Transfer amount from one goal to another. Both must exist and from must have enough."""
    from_g = get_goal(session, from_goal_id)
    to_g = get_goal(session, to_goal_id)
    if not from_g or not to_g or from_goal_id == to_goal_id:
        return False
    if amount <= 0 or (from_g.current_amount or 0) < amount:
        return False
    from_g.current_amount = (from_g.current_amount or 0) - amount
    to_g.current_amount = (to_g.current_amount or 0) + amount
    session.commit()
    return True


# Subscription
def get_active_subscriptions(session: Session) -> list:
    return session.query(Subscription).filter(Subscription.is_active == True).all()


def get_inactive_subscriptions(session: Session) -> list:
    return session.query(Subscription).filter(Subscription.is_active == False).all()


def get_subscription(session: Session, sub_id: str):
    return session.query(Subscription).filter(Subscription.id == sub_id).first()


def update_subscription(session: Session, sub_id: str, **kwargs) -> bool:
    s = get_subscription(session, sub_id)
    if not s:
        return False
    for k, v in kwargs.items():
        if hasattr(s, k):
            if k == "next_date" and v is not None:
                setattr(s, k, v[:10] if v else s.next_date)
            else:
                setattr(s, k, v)
    session.commit()
    return True


def delete_subscription(session: Session, sub_id: str) -> bool:
    s = get_subscription(session, sub_id)
    if not s:
        return False
    session.delete(s)
    session.commit()
    return True


def add_subscription(
    session: Session,
    name: str,
    amount: float,
    cycle: str,
    next_date: str,
    remind_days_before: int = 1,
    category: str = "Прочее",
) -> str:
    rid = generate_id()
    session.add(Subscription(
        id=rid, name=name, amount=amount, cycle=cycle,
        next_date=next_date[:10], remind_days_before=remind_days_before,
        category=category,
    ))
    session.commit()
    return rid


def get_subscriptions_due_soon(session: Session, today_str: str, days_ahead: int = 3) -> list:
    """Subscriptions with next_date within days_ahead from today."""
    from datetime import datetime, timedelta
    try:
        parts = today_str[:10].split("-")
        end_dt = datetime(int(parts[0]), int(parts[1]), int(parts[2])) + timedelta(days=days_ahead)
        end_str = end_dt.strftime("%Y-%m-%d")
    except (ValueError, IndexError):
        return []
    return session.query(Subscription).filter(
        Subscription.is_active == True,
        Subscription.next_date >= today_str[:10],
        Subscription.next_date <= end_str,
    ).all()


def advance_subscription_date(session: Session, sub_id: str) -> bool:
    """Move next_date forward by one cycle."""
    from datetime import datetime, timedelta
    s = session.query(Subscription).filter(Subscription.id == sub_id).first()
    if not s:
        return False
    try:
        dt = datetime.strptime(s.next_date[:10], "%Y-%m-%d")
        if s.cycle == "monthly":
            if dt.month == 12:
                dt = dt.replace(year=dt.year + 1, month=1)
            else:
                dt = dt.replace(month=dt.month + 1)
        elif s.cycle == "weekly":
            dt = dt + timedelta(days=7)
        elif s.cycle == "yearly":
            dt = dt.replace(year=dt.year + 1)
        else:
            dt = dt + timedelta(days=30)
        s.next_date = dt.strftime("%Y-%m-%d")
        session.commit()
        return True
    except Exception:
        return False


# Finance - last entry and update/delete
def get_last_finance_entry(session: Session, entry_type: str = None, limit: int = 1) -> list:
    q = session.query(Finance).filter(Finance.is_deleted == False).order_by(
        Finance.date.desc(), Finance.id.desc()
    )
    if entry_type:
        q = q.filter(Finance.type == entry_type)
    return q.limit(limit).all()


def get_finance_by_id(session: Session, fid: str, include_deleted: bool = False):
    q = session.query(Finance).filter(Finance.id == fid)
    if not include_deleted:
        q = q.filter(Finance.is_deleted == False)
    return q.first()


def log_audit(session: Session, chat_id: str, entity: str, entity_id: str, action: str, field: str = None, old_value=None, new_value=None):
    session.add(AuditLog(
        chat_id=str(chat_id),
        entity=entity,
        entity_id=entity_id,
        action=action,
        field=field,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
    ))
    session.commit()


def mass_finance_operations(session: Session, start_str: str, end_str: str, category: str = None,
                           action: str = "soft_delete") -> int:
    """action: soft_delete or exclude_from_budget. Returns count of affected rows."""
    q = session.query(Finance).filter(
        Finance.date >= start_str, Finance.date <= end_str,
        Finance.is_deleted == False,
    )
    if category and category != "all":
        q = q.filter(Finance.category == category)
    rows = q.all()
    count = 0
    for r in rows:
        if action == "soft_delete":
            r.is_deleted = True
            count += 1
        elif action == "exclude_from_budget" and r.type == "Expense":
            r.exclude_from_budget = True
            count += 1
    session.commit()
    return count


def soft_delete_finance_entry(session: Session, fid: str) -> bool:
    r = session.query(Finance).filter(Finance.id == fid).first()
    if not r:
        return False
    r.is_deleted = True
    session.commit()
    return True


def has_finance_duplicate(session: Session, date_str: str, amount: float) -> bool:
    """Check if record with same date and amount exists (for import dedup)."""
    date_norm = date_str[:10] if date_str else ""
    if not date_norm:
        return False
    q = session.query(Finance).filter(Finance.date == date_norm, Finance.amount == amount)
    q = q.filter(Finance.is_deleted == False)
    return q.first() is not None


def update_finance_entry(session: Session, fid: str, amount: float = None, category: str = None, comment: str = None,
                        date: str = None, entry_type: str = None, exclude_from_budget: bool = None) -> bool:
    r = session.query(Finance).filter(Finance.id == fid).first()
    if not r:
        return False
    if amount is not None:
        r.amount = amount
    if category is not None:
        r.category = category
    if comment is not None:
        r.comment = comment
    if date is not None:
        r.date = date[:10]
    if entry_type is not None:
        r.type = entry_type
    if exclude_from_budget is not None:
        r.exclude_from_budget = exclude_from_budget
    session.commit()
    return True


def delete_finance_entry(session: Session, fid: str) -> bool:
    r = get_finance_by_id(session, fid)
    if not r:
        return False
    session.delete(r)
    session.commit()
    return True


def get_expenses_by_category_for_period(session: Session, start_str: str, end_str: str) -> dict:
    """Returns {category: total_amount} for Expense type, excluding exclude_from_budget."""
    rows = get_finance_for_period(session, start_str, end_str)
    result = {}
    for r in rows:
        if r.type == "Expense" and r.category and not getattr(r, "exclude_from_budget", False):
            result[r.category] = result.get(r.category, 0) + (r.amount or 0)
    return result


# Debt
def add_debt(
    session: Session, direction: str, counterparty: str, original_amount: float,
    interest_rate: float = 0, payment_type: str = "fixed",
    monthly_payment: float = 0, payment_cycle: str = "monthly",
    next_payment_date: str = "", debt_kind: str = "credit", due_date: str = "",
) -> str:
    rid = generate_id()
    session.add(Debt(
        id=rid, direction=direction, counterparty=counterparty,
        original_amount=original_amount, remaining_amount=original_amount,
        interest_rate=interest_rate, payment_type=payment_type,
        monthly_payment=monthly_payment, payment_cycle=payment_cycle or "monthly",
        next_payment_date=next_payment_date[:10] if next_payment_date else None,
        debt_kind=debt_kind or "credit", due_date=due_date or "",
    ))
    session.commit()
    return rid


def get_active_debts(session: Session) -> list:
    return session.query(Debt).filter(Debt.is_active == True).all()


def get_debt(session: Session, debt_id: str):
    return session.query(Debt).filter(Debt.id == debt_id).first()


def add_debt_payment(session: Session, debt_id: str, amount: float, comment: str = "", date: str = None) -> str | None:
    debt = get_debt(session, debt_id)
    if not debt:
        return None
    pid = generate_id()
    date_str = (date[:10] if date else None) or get_today_msk()
    session.add(DebtPayment(id=pid, debt_id=debt_id, date=date_str, amount=amount, comment=comment))
    debt.remaining_amount = max(0, (debt.remaining_amount or 0) - amount)
    if debt.remaining_amount <= 0:
        debt.is_active = False
    else:
        if date_str == get_today_msk():
            advance_debt_next_date(session, debt_id)
    session.commit()
    return pid


def get_debt_payment(session: Session, payment_id: str):
    return session.query(DebtPayment).filter(DebtPayment.id == payment_id).first()


def update_debt_payment(session: Session, payment_id: str, amount: float = None, date: str = None) -> bool:
    p = get_debt_payment(session, payment_id)
    if not p:
        return False
    if amount is not None:
        delta = amount - p.amount
        p.amount = amount
        debt = get_debt(session, p.debt_id)
        if debt:
            debt.remaining_amount = max(0, (debt.remaining_amount or 0) + delta)
            if debt.remaining_amount > 0 and not debt.is_active:
                debt.is_active = True
    if date is not None:
        p.date = date[:10]
    session.commit()
    return True


def delete_debt_payment(session: Session, payment_id: str) -> bool:
    p = get_debt_payment(session, payment_id)
    if not p:
        return False
    debt = get_debt(session, p.debt_id)
    if debt:
        debt.remaining_amount = (debt.remaining_amount or 0) + p.amount
        debt.is_active = True
    session.delete(p)
    session.commit()
    return True


def update_debt(session: Session, debt_id: str, **kwargs) -> bool:
    debt = get_debt(session, debt_id)
    if not debt:
        return False
    for k, v in kwargs.items():
        if hasattr(debt, k):
            if k == "next_payment_date" and v is not None:
                setattr(debt, k, v[:10] if v else None)
            elif k == "due_date" and v is not None:
                setattr(debt, k, v[:10] if v else "")
            else:
                setattr(debt, k, v)
    session.commit()
    return True


def update_debt_remaining_with_comment(session: Session, debt_id: str, new_remaining: float, comment: str) -> bool:
    debt = get_debt(session, debt_id)
    if not debt:
        return False
    debt.remaining_amount = max(0, new_remaining)
    if debt.remaining_amount <= 0:
        debt.is_active = False
    else:
        debt.is_active = True
    session.commit()
    return True


def get_debt_payments(session: Session, debt_id: str) -> list:
    return session.query(DebtPayment).filter(DebtPayment.debt_id == debt_id).all()


def get_debts_due_today(session: Session) -> list:
    """Debts with due_date or next_payment_date matching today."""
    today = get_today_msk()
    debts = session.query(Debt).filter(Debt.is_active == True).all()
    return [d for d in debts if (d.due_date == today) or (getattr(d, "next_payment_date", None) == today)]


def advance_debt_next_date(session: Session, debt_id: str) -> bool:
    """Move next_payment_date forward by one cycle after payment."""
    from datetime import datetime, timedelta
    d = get_debt(session, debt_id)
    if not d or not getattr(d, "next_payment_date", None):
        return False
    try:
        dt = datetime.strptime(d.next_payment_date[:10], "%Y-%m-%d")
        cycle = getattr(d, "payment_cycle", "monthly") or "monthly"
        if cycle == "biweekly":
            dt = dt + timedelta(days=14)
        else:
            if dt.month == 12:
                dt = dt.replace(year=dt.year + 1, month=1)
            else:
                dt = dt.replace(month=dt.month + 1)
        d.next_payment_date = dt.strftime("%Y-%m-%d")
        session.commit()
        return True
    except Exception:
        return False


def get_debt_summary(session: Session) -> dict:
    debts = get_active_debts(session)
    owe = sum(d.remaining_amount for d in debts if d.direction == "owe")
    lent = sum(d.remaining_amount for d in debts if d.direction == "lent")
    return {"owe": owe, "lent": lent, "count": len(debts)}


# Category
def get_categories_tree(session: Session) -> list:
    return session.query(Category).order_by(Category.parent_id, Category.name).all()


def get_root_categories(session: Session) -> list:
    return session.query(Category).filter(Category.parent_id == None).order_by(Category.usage_count.desc()).all()


def get_subcategories(session: Session, parent_id: str) -> list:
    return session.query(Category).filter(Category.parent_id == parent_id).all()


def add_category(session: Session, name: str, parent_id: str = None, is_system: bool = False) -> str:
    rid = generate_id()
    session.add(Category(id=rid, name=name, parent_id=parent_id, is_system=is_system))
    session.commit()
    return rid


def get_top_categories(session: Session, limit: int = 3) -> list:
    return session.query(Category).order_by(Category.usage_count.desc()).limit(limit).all()


def increment_category_usage(session: Session, name: str):
    cat = session.query(Category).filter(Category.name == name).first()
    if cat:
        cat.usage_count = (cat.usage_count or 0) + 1
        session.commit()


def get_category_by_name(session: Session, name: str):
    return session.query(Category).filter(Category.name == name).first()


# Tag
def add_tag(session: Session, name: str) -> str:
    existing = session.query(Tag).filter(Tag.name == name).first()
    if existing:
        return existing.id
    rid = generate_id()
    session.add(Tag(id=rid, name=name))
    session.commit()
    return rid


def update_tag(session: Session, tag_id: str, name: str) -> bool:
    t = session.query(Tag).filter(Tag.id == tag_id).first()
    if not t:
        return False
    t.name = name
    session.commit()
    return True


def delete_tag(session: Session, tag_id: str) -> bool:
    t = session.query(Tag).filter(Tag.id == tag_id).first()
    if not t:
        return False
    session.delete(t)
    session.commit()
    return True


def get_tags(session: Session) -> list:
    return session.query(Tag).all()


# ExpenseTemplate
def get_templates(session: Session) -> list:
    return session.query(ExpenseTemplate).order_by(ExpenseTemplate.usage_count.desc()).all()


def get_template(session: Session, template_id: str):
    return session.query(ExpenseTemplate).filter(ExpenseTemplate.id == template_id).first()


def update_template(session: Session, template_id: str, **kwargs) -> bool:
    t = get_template(session, template_id)
    if not t:
        return False
    for k, v in kwargs.items():
        if hasattr(t, k):
            setattr(t, k, v)
    session.commit()
    return True


def delete_template(session: Session, template_id: str) -> bool:
    t = get_template(session, template_id)
    if not t:
        return False
    session.delete(t)
    session.commit()
    return True


def add_template(session: Session, name: str, amount: float, category: str) -> str:
    rid = generate_id()
    session.add(ExpenseTemplate(id=rid, name=name, amount=amount, category=category))
    session.commit()
    return rid


def use_template(session: Session, template_id: str) -> Optional[dict]:
    t = session.query(ExpenseTemplate).filter(ExpenseTemplate.id == template_id).first()
    if not t:
        return None
    t.usage_count = (t.usage_count or 0) + 1
    session.commit()
    return {"name": t.name, "amount": t.amount, "category": t.category}


# Goal extensions
def archive_goal(session: Session, goal_id: str) -> bool:
    g = session.query(Goal).filter(Goal.id == goal_id).first()
    if not g:
        return False
    g.is_archived = True
    g.is_active = False
    session.commit()
    return True


def get_archived_goals(session: Session) -> list:
    return session.query(Goal).filter(Goal.is_archived == True).all()


def get_goals_for_auto_fund(session: Session) -> list:
    return session.query(Goal).filter(
        Goal.is_active == True, Goal.is_archived == False
    ).filter(
        (Goal.auto_fund_percent > 0) | (Goal.auto_fund_amount > 0)
    ).all()


# Subscription extensions
def get_overdue_subscriptions(session: Session) -> list:
    today = get_today_msk()
    return session.query(Subscription).filter(
        Subscription.is_active == True, Subscription.next_date < today
    ).all()


def get_subscriptions_by_group(session: Session, group: str) -> list:
    return session.query(Subscription).filter(
        Subscription.is_active == True, Subscription.group == group
    ).all()


def process_due_subscriptions(session: Session, today_str: str) -> list:
    """Auto-create expense/income for due subscriptions and advance dates."""
    subs = session.query(Subscription).filter(
        Subscription.is_active == True,
        Subscription.auto_create_expense == True,
        Subscription.next_date <= today_str,
    ).all()
    created = []
    for s in subs:
        entry_type = "Expense" if s.sub_type == "expense" else "IncomeSecond"
        add_finance_entry(session, today_str, entry_type, s.amount, s.category or "Подписки", f"Авто: {s.name}")
        advance_subscription_date(session, s.id)
        created.append({"name": s.name, "amount": s.amount, "type": entry_type})
    return created


# Finance history/search
def get_finance_history(session: Session, limit: int = 20) -> list:
    return session.query(Finance).filter(Finance.is_deleted == False).order_by(
        Finance.date.desc(), Finance.id.desc()
    ).limit(limit).all()


def search_finance(session: Session, query: str, limit: int = 20) -> list:
    q = f"%{query}%"
    return session.query(Finance).filter(
        Finance.is_deleted == False,
        (Finance.comment.like(q)) | (Finance.category.like(q))
    ).order_by(Finance.date.desc()).limit(limit).all()


# Achievement
def get_achievements(session: Session) -> list:
    return session.query(Achievement).all()


def delete_achievement(session: Session, achievement_id: int) -> bool:
    a = session.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not a:
        return False
    session.delete(a)
    session.commit()
    return True


# Calculation
def get_calculations(session: Session, limit: int = 20) -> list:
    return session.query(Calculation).order_by(Calculation.id.desc()).limit(limit).all()


def get_calculation(session: Session, calc_id: int):
    return session.query(Calculation).filter(Calculation.id == calc_id).first()


def update_calculation(session: Session, calc_id: int, **kwargs) -> bool:
    c = get_calculation(session, calc_id)
    if not c:
        return False
    for k, v in kwargs.items():
        if hasattr(c, k):
            setattr(c, k, v)
    session.commit()
    return True


# Seed system categories
def seed_system_categories(session: Session):
    """Create system categories if they don't exist."""
    system_cats = ["Еда", "Транспорт", "ЗП Выплата", "Жильё", "Здоровье", "Развлечения", "Прочее",
                   "Кафе", "Рестораны", "Продукты", "Такси", "Аптека", "Одежда", "Подписки"]
    for name in system_cats:
        existing = session.query(Category).filter(Category.name == name).first()
        if not existing:
            session.add(Category(id=generate_id(), name=name, is_system=True))
    session.commit()
