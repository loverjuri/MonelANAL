"""Database repositories for CRUD operations."""
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from db.models import (
    Base, engine, SessionLocal, get_session, generate_id,
    Config, WorkLog, Order, Finance, State, Log, Calculation,
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
