"""Scheduled prompts: main work, second job, payday, reminders."""
from services.calculations import get_today_msk, get_accrued_summary_for_payday
from services.state import get_state, set_state
from db.repositories import get_session, has_work_log_for_date, has_orders_for_date
from bot.telegram_api import send_message
from bot.keyboards import (
    build_main_work_keyboard,
    build_second_job_keyboard,
)


def send_main_work_prompt(chat_id: int):
    """18:00 — How was your work day?"""
    send_message(chat_id, "Как прошёл рабочий день?", build_main_work_keyboard())


def send_second_job_prompt(chat_id: int):
    """00:05 — Second job income for yesterday?"""
    send_message(chat_id, "Доходы со второй работы за вчера?", build_second_job_keyboard())


def send_payday_prompt(chat_id: int):
    """10:00 on 10th/25th — How much received?"""
    session = get_session()
    try:
        acc = get_accrued_summary_for_payday(session)
        msg = (
            f"Накоплено к выплате: {int(acc['accruedTotal'])} руб.\n"
            f"(основная: {int(acc['accruedMain'])}, вторая: {int(acc['accruedSecond'])})\n\n"
            "Сколько фактически пришло на карту? (введите число)"
        )
        set_state(chat_id, "payday_amount", "0", {
            "accrued": {"main": acc["accruedMain"], "second": acc["accruedSecond"]},
            "periodStart": acc["periodStart"],
            "periodEnd": acc["periodEnd"],
        })
        send_message(chat_id, msg)
    except Exception:
        send_message(chat_id, "Ошибка расчёта накоплений.")
    finally:
        session.close()


def send_reminder_main_work(chat_id: int):
    """19:00 — Reminder if no main work log for today."""
    session = get_session()
    try:
        today = get_today_msk()
        if not has_work_log_for_date(session, today, "Main"):
            send_message(chat_id, "Напоминание: как прошёл рабочий день?", build_main_work_keyboard())
    finally:
        session.close()


def send_reminder_second_job(chat_id: int):
    """00:30 — Reminder if no orders for yesterday."""
    session = get_session()
    try:
        from services.calculations import get_yesterday_msk
        yesterday = get_yesterday_msk()
        if not has_orders_for_date(session, yesterday):
            send_message(chat_id, "Напоминание: доходы со второй работы за вчера?", build_second_job_keyboard())
    finally:
        session.close()
