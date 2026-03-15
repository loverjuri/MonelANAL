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
) -> str:
    rid = generate_id()
    session.add(Finance(
        id=rid,
        date=date_str[:10],
        type=entry_type,
        amount=amount,
        category=category or "",
        comment=comment or "",
    ))
    session.commit()
    return rid


def get_finance_for_period(session: Session, start_str: str, end_str: str):
    return session.query(Finance).filter(
        Finance.date >= start_str,
        Finance.date <= end_str,
    ).all()


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


# Logs
def log_info(session: Session, message: str):
    session.add(Log(level="Info", message=message))
    session.commit()


def log_error(session: Session, message: str):
    session.add(Log(level="Error", message=message))
    session.commit()


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


def get_goal(session: Session, goal_id: str):
    return session.query(Goal).filter(Goal.id == goal_id).first()


# Subscription
def get_active_subscriptions(session: Session) -> list:
    return session.query(Subscription).filter(Subscription.is_active == True).all()


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
    q = session.query(Finance).order_by(Finance.date.desc(), Finance.id.desc())
    if entry_type:
        q = q.filter(Finance.type == entry_type)
    return q.limit(limit).all()


def get_finance_by_id(session: Session, fid: str):
    return session.query(Finance).filter(Finance.id == fid).first()


def update_finance_entry(session: Session, fid: str, amount: float = None, category: str = None, comment: str = None) -> bool:
    r = get_finance_by_id(session, fid)
    if not r:
        return False
    if amount is not None:
        r.amount = amount
    if category is not None:
        r.category = category
    if comment is not None:
        r.comment = comment
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
    """Returns {category: total_amount} for Expense type."""
    rows = get_finance_for_period(session, start_str, end_str)
    result = {}
    for r in rows:
        if r.type == "Expense" and r.category:
            result[r.category] = result.get(r.category, 0) + (r.amount or 0)
    return result


# Debt
def add_debt(
    session: Session, direction: str, counterparty: str, original_amount: float,
    interest_rate: float = 0, payment_type: str = "fixed",
    monthly_payment: float = 0, due_date: str = "",
) -> str:
    rid = generate_id()
    session.add(Debt(
        id=rid, direction=direction, counterparty=counterparty,
        original_amount=original_amount, remaining_amount=original_amount,
        interest_rate=interest_rate, payment_type=payment_type,
        monthly_payment=monthly_payment, due_date=due_date or "",
    ))
    session.commit()
    return rid


def get_active_debts(session: Session) -> list:
    return session.query(Debt).filter(Debt.is_active == True).all()


def get_debt(session: Session, debt_id: str):
    return session.query(Debt).filter(Debt.id == debt_id).first()


def add_debt_payment(session: Session, debt_id: str, amount: float, comment: str = "") -> str | None:
    debt = get_debt(session, debt_id)
    if not debt:
        return None
    pid = generate_id()
    session.add(DebtPayment(id=pid, debt_id=debt_id, date=get_today_msk(), amount=amount, comment=comment))
    debt.remaining_amount = max(0, (debt.remaining_amount or 0) - amount)
    if debt.remaining_amount <= 0:
        debt.is_active = False
    session.commit()
    return pid


def get_debt_payments(session: Session, debt_id: str) -> list:
    return session.query(DebtPayment).filter(DebtPayment.debt_id == debt_id).all()


def get_debts_due_today(session: Session) -> list:
    today = get_today_msk()
    return session.query(Debt).filter(Debt.is_active == True, Debt.due_date == today).all()


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


def get_tags(session: Session) -> list:
    return session.query(Tag).all()


# ExpenseTemplate
def get_templates(session: Session) -> list:
    return session.query(ExpenseTemplate).order_by(ExpenseTemplate.usage_count.desc()).all()


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
    return session.query(Finance).order_by(Finance.date.desc(), Finance.id.desc()).limit(limit).all()


def search_finance(session: Session, query: str, limit: int = 20) -> list:
    q = f"%{query}%"
    return session.query(Finance).filter(
        (Finance.comment.like(q)) | (Finance.category.like(q))
    ).order_by(Finance.date.desc()).limit(limit).all()


# Achievement
def get_achievements(session: Session) -> list:
    return session.query(Achievement).all()


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
