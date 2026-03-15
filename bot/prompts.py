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


def send_subscriptions_reminder(chat_id: int):
    """Daily — Subscriptions due in next 3 days."""
    from db.repositories import get_subscriptions_due_soon
    from services.calculations import get_today_msk
    session = get_session()
    try:
        today = get_today_msk()
        subs = get_subscriptions_due_soon(session, today, 3)
        if subs:
            lines = ["Ближайшие платежи:"]
            for s in subs:
                lines.append(f"• {s.name}: {int(s.amount)} руб. — {s.next_date}")
            send_message(chat_id, "\n".join(lines))
    finally:
        session.close()


def send_overspend_digest(chat_id: int):
    """Daily digest with overspend, recommendations, goal hints."""
    from services.notifications import should_send_now
    session = get_session()
    try:
        if not should_send_now(session):
            return
        from services.recommendations import generate_daily_digest
        digest = generate_daily_digest(session)
        if digest:
            send_message(chat_id, digest)
    except Exception:
        from services.budget import get_budget_status
        st = get_budget_status(session)
        if st["over"]:
            lines = ["⚠ Перерасход по категориям:"]
            for o in st["over"]:
                lines.append(f"• {o['category']}: лимит {int(o['limit'])}, потрачено {int(o['spent'])} (+{int(o['over'])})")
            send_message(chat_id, "\n".join(lines))
    finally:
        session.close()


def send_debt_reminders(chat_id: int):
    """Daily — Debts due today."""
    from db.repositories import get_debts_due_today
    from services.notifications import should_send_now
    session = get_session()
    try:
        if not should_send_now(session):
            return
        debts = get_debts_due_today(session)
        if debts:
            lines = ["Напоминание о долгах:"]
            for d in debts:
                direction = "Вы должны" if d.direction == "owe" else "Вам должны"
                lines.append(f"• {direction} {d.counterparty}: {int(d.remaining_amount)} руб.")
            send_message(chat_id, "\n".join(lines))
    finally:
        session.close()


def send_goal_deadline_reminder(chat_id: int):
    """Monthly — Goals approaching deadline."""
    from db.repositories import get_active_goals
    from services.notifications import should_send_now
    from services.calculations import get_today_msk
    from datetime import datetime, timedelta
    session = get_session()
    try:
        if not should_send_now(session):
            return
        today = get_today_msk()
        threshold = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
        goals = get_active_goals(session)
        approaching = [g for g in goals if g.deadline and g.deadline <= threshold and g.current_amount < g.target_amount]
        if approaching:
            lines = ["Цели с приближающимся сроком:"]
            for g in approaching:
                remaining = int(g.target_amount - g.current_amount)
                lines.append(f"• {g.name}: осталось {remaining} руб. (срок {g.deadline})")
            send_message(chat_id, "\n".join(lines))
    finally:
        session.close()


def send_auto_backup(chat_id: int):
    """Daily — Auto backup."""
    from services.notifications import should_send_now
    import os
    session = get_session()
    try:
        if not should_send_now(session):
            return
        from services.backup import create_backup_json
        from bot.telegram_api import send_document
        path = create_backup_json(session)
        send_document(chat_id, path, "Ежедневный бэкап MonelANAL")
        try:
            os.unlink(path)
        except Exception:
            pass
    finally:
        session.close()


def send_auto_subscriptions(chat_id: int):
    """Daily — Process auto-create subscriptions."""
    from db.repositories import process_due_subscriptions
    from services.calculations import get_today_msk
    from services.notifications import should_send_now
    session = get_session()
    try:
        if not should_send_now(session):
            return
        today = get_today_msk()
        created = process_due_subscriptions(session, today)
        if created:
            lines = ["Авто-списания:"]
            for c in created:
                lines.append(f"• {c['name']}: {int(c['amount'])} руб.")
            send_message(chat_id, "\n".join(lines))
    finally:
        session.close()
