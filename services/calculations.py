"""Business logic for salary accrual, budget, pay dates."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from db.repositories import (
    get_config_param,
    get_work_log_for_period,
    sum_orders_for_period,
    get_finance_for_period,
)

TZ = ZoneInfo("Europe/Moscow")


def _get_fixed_salary(session) -> float:
    v = get_config_param(session, "FixedSalary")
    return float(v) if v else 0


def _get_pay_day1(session) -> int:
    v = get_config_param(session, "PayDay1")
    return int(v) if v else 10


def _get_pay_day2(session) -> int:
    v = get_config_param(session, "PayDay2")
    return int(v) if v else 25


def _get_work_hours_norm(session) -> int:
    v = get_config_param(session, "WorkHoursNorm")
    return int(v) if v else 8


def format_date_for_compare(d) -> str:
    if isinstance(d, str):
        return d[:10] if len(d) >= 10 else d
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def get_today_msk() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def get_yesterday_msk() -> str:
    return (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")


def add_days(date_str: str, days: int) -> str:
    parts = date_str[:10].split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    dt = datetime(y, m, d) + timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def get_last_pay_date(today_str: str, session) -> str:
    parts = today_str[:10].split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    pay1 = _get_pay_day1(session)
    pay2 = _get_pay_day2(session)
    cand1 = f"{y}-{m:02d}-{pay1:02d}"
    cand2 = f"{y}-{m:02d}-{pay2:02d}"
    if today_str >= cand2:
        return cand2
    if today_str >= cand1:
        return cand1
    prev_m = 12 if m == 1 else m - 1
    prev_y = y - 1 if m == 1 else y
    prev_cand2 = f"{prev_y}-{prev_m:02d}-{pay2:02d}"
    prev_cand1 = f"{prev_y}-{prev_m:02d}-{pay1:02d}"
    if pay2 > pay1:
        return prev_cand2 if today_str >= prev_cand2 else prev_cand1
    return prev_cand1 if today_str >= prev_cand1 else prev_cand2


def get_accrual_period_start(today_str: str, session) -> str:
    last_pay = get_last_pay_date(today_str, session)
    return add_days(last_pay, 1)


def get_accrued_main_for_period(start_str: str, end_str: str, session) -> float:
    rows = get_work_log_for_period(session, start_str, end_str, job_type="Main")
    total = 0
    for r in rows:
        if r.status == "Sick" and not r.is_paid:
            continue
        total += (r.hours_worked or 0) * (r.hour_rate_snapshot or 0)
    return total


def get_accrued_second_for_period(start_str: str, end_str: str, session) -> float:
    return sum_orders_for_period(session, start_str, end_str)


def get_accrued_total(start_str: str, end_str: str, session) -> dict:
    main = get_accrued_main_for_period(start_str, end_str, session)
    second = get_accrued_second_for_period(start_str, end_str, session)
    return {"main": main, "second": second, "total": main + second}


def get_accrued_summary_for_payday(session) -> dict:
    today = get_today_msk()
    start = get_accrual_period_start(today, session)
    end = today
    acc = get_accrued_total(start, end, session)
    return {
        "periodStart": start,
        "periodEnd": end,
        "accruedMain": acc["main"],
        "accruedSecond": acc["second"],
        "accruedTotal": acc["total"],
    }


def get_next_pay_date(today_str: str, session) -> str:
    parts = today_str[:10].split("-")
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    pay1 = _get_pay_day1(session)
    pay2 = _get_pay_day2(session)
    cand1 = f"{y}-{m:02d}-{pay1:02d}"
    cand2 = f"{y}-{m:02d}-{pay2:02d}"
    if today_str < cand1:
        return cand1
    if today_str < cand2:
        return cand2
    next_m = 1 if m == 12 else m + 1
    next_y = y + 1 if m == 12 else y
    return f"{next_y}-{next_m:02d}-{pay1:02d}"


TYPE_INCOME_SALARY = "IncomeSalary"
TYPE_INCOME_SECOND = "IncomeSecond"
TYPE_EXPENSE = "Expense"


def get_budget_balance(session) -> float:
    rows = get_finance_for_period(session, "2000-01-01", "2099-12-31")
    income = expense = 0
    for r in rows:
        amt = r.amount or 0
        if r.type in (TYPE_INCOME_SALARY, TYPE_INCOME_SECOND):
            income += amt
        elif r.type == TYPE_EXPENSE:
            expense += amt
    return income - expense


def calc_hour_rate_snapshot_for_date(date_str: str, session) -> float:
    """FixedSalary / MonthNormHours for the month of date_str."""
    from services.prod_calendar import get_month_norm_hours_for_date
    norm = get_month_norm_hours_for_date(date_str, session)
    if norm <= 0:
        norm = _get_work_hours_norm(session) * 21
    salary = _get_fixed_salary(session)
    return salary / norm if norm else 0
