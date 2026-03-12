"""Message and callback handlers. FSM logic."""
from db.repositories import (
    get_session,
    add_work_log,
    add_order,
    add_order_with_items,
    add_finance_entry,
    record_payday_received,
    get_orders_for_period,
    log_info,
    log_error,
)
from services.state import get_state, set_state, clear_state
from services.calculations import (
    get_today_msk as calc_today,
    get_yesterday_msk as calc_yesterday,
    get_accrued_summary_for_payday,
    get_next_pay_date,
    get_budget_balance,
    get_accrued_second_for_period,
    calc_hour_rate_snapshot_for_date,
)
from bot.telegram_api import send_message, answer_callback_query
from bot.keyboards import (
    build_main_menu_keyboard,
    build_main_work_keyboard,
    build_second_job_keyboard,
    build_expense_categories_keyboard,
    build_expense_comment_keyboard,
    build_income_comment_keyboard,
    build_yes_no_keyboard,
    build_hours_quick_keyboard,
    build_cancel_keyboard,
    build_status_keyboard,
    EXPENSE_CATEGORIES,
)

from config import get_chat_id

JOB_MAIN = "Main"
STATUS_WORK = "Work"
STATUS_SICK = "Sick"
STATUS_WEEKEND_WORK = "WeekendWork"
TYPE_EXPENSE = "Expense"
TYPE_INCOME_SECOND = "IncomeSecond"


def is_authorized_chat(chat_id) -> bool:
    allowed = get_chat_id()
    if not allowed:
        return True
    return str(chat_id) == str(allowed).strip()


def is_exit_command(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in (
        "/start", "/help", "/помощь", "справка", "отмена", "/cancel",
        "статус", "расход", "доход",
    )


def handle_message(chat_id: int, text: str, message_id: int | None = None):
    session = get_session()
    try:
        state = get_state(chat_id)
        trimmed = (text or "").strip()
        if trimmed:
            log_info(session, f"handleMessage: chatId={chat_id} text={trimmed[:50]}")

        if state and is_exit_command(trimmed):
            clear_state(chat_id)
            send_message(chat_id, "Выберите действие:", build_main_menu_keyboard())
            return

        if state and state.get("scenario") == "main_hours":
            try:
                hours = float(trimmed.replace(",", "."))
            except ValueError:
                hours = float("nan")
            if not (hours != hours) and 0 <= hours <= 24:
                date_str = state.get("payload", {}).get("date") or calc_today()
                is_weekend = state.get("payload", {}).get("weekend") is True
                status = STATUS_WEEKEND_WORK if is_weekend else STATUS_WORK
                hour_rate = calc_hour_rate_snapshot_for_date(date_str, session)
                add_work_log(session, date_str, JOB_MAIN, hours, status, hour_rate)
                clear_state(chat_id)
                send_message(chat_id, f"Записано: {hours} ч.")
                return
            send_message(chat_id, "Введите число часов от 0 до 24.")
            return

        if state and state.get("scenario") == "second_order":
            if state.get("step") == "description":
                set_state(chat_id, "second_order", "amount", {
                    "date": state["payload"].get("date"),
                    "description": trimmed,
                })
                send_message(chat_id, "Введите сумму заказа (число):")
                return
            if state.get("step") == "amount":
                try:
                    amount = float(trimmed.replace(" ", "").replace(",", "."))
                except ValueError:
                    amount = float("nan")
                if not (amount != amount) and amount >= 0:
                    desc = state["payload"].get("description", "")
                    items = state["payload"].get("items") or []
                    items.append({"description": desc, "amount": amount})
                    set_state(chat_id, "second_order", "more", {
                        "date": state["payload"]["date"],
                        "items": items,
                    })
                    send_message(chat_id, "Ещё позиции в этот заказ?", build_yes_no_keyboard())
                    return
                send_message(chat_id, "Введите число (сумма).")
                return
            if state.get("step") == "more" and trimmed.lower() in ("да", "нет"):
                if trimmed.lower() == "нет":
                    add_order_with_items(session, state["payload"]["date"], state["payload"].get("items", []))
                    clear_state(chat_id)
                    send_message(chat_id, "Заказ сохранён.")
                else:
                    set_state(chat_id, "second_order", "description", {
                        "date": state["payload"]["date"],
                        "items": state["payload"].get("items", []),
                    })
                    send_message(chat_id, "Введите описание следующей позиции:")
                return

        if state and state.get("scenario") == "payday_amount":
            try:
                received = float(trimmed.replace(" ", "").replace(",", "."))
            except ValueError:
                received = float("nan")
            if not (received != received) and received >= 0:
                acc = state["payload"].get("accrued") or {}
                record_payday_received(
                    session,
                    calc_today(),
                    received,
                    acc.get("main", 0),
                    acc.get("second", 0),
                    state["payload"].get("periodStart", ""),
                    state["payload"].get("periodEnd", ""),
                )
                clear_state(chat_id)
                send_message(chat_id, f"Сумма {received} руб. записана. Корректировка при необходимости внесена.")
                return
            send_message(chat_id, "Введите число (сумма, полученная на карту).")
            return

        if state and state.get("scenario") == "expense_comment":
            amount = state["payload"]["amount"]
            category = state["payload"]["category"]
            comment = "" if trimmed in ("-", "пропустить", "нет") else trimmed
            add_finance_entry(session, calc_today(), TYPE_EXPENSE, amount, category, comment)
            clear_state(chat_id)
            send_message(
                chat_id,
                f"Расход записан: {amount} руб., {category}" + (f", {comment}" if comment else "") + ".",
            )
            return

        if state and state.get("scenario") == "expense_amount":
            try:
                amt = float(trimmed.replace(" ", "").replace(",", "."))
            except ValueError:
                amt = float("nan")
            if not (amt != amt) and amt > 0:
                set_state(chat_id, "expense_cat", "0", {"amount": amt})
                send_message(chat_id, "Выберите категорию:", build_expense_categories_keyboard())
                return
            send_message(chat_id, "Введите сумму расхода (положительное число).", build_cancel_keyboard())
            return

        if state and state.get("scenario") == "income_comment":
            amount = state["payload"]["amount"]
            comment = "" if trimmed in ("-", "пропустить", "нет") else trimmed
            add_finance_entry(session, calc_today(), TYPE_INCOME_SECOND, amount, "Прочее", comment)
            clear_state(chat_id)
            send_message(chat_id, f"Доход записан: {amount} руб." + (f" ({comment})" if comment else "") + ".")
            return

        if state and state.get("scenario") == "income_amount":
            try:
                amt = float(trimmed.replace(" ", "").replace(",", "."))
            except ValueError:
                amt = float("nan")
            if not (amt != amt) and amt > 0:
                set_state(chat_id, "income_comment", "0", {"amount": amt})
                send_message(chat_id, "Комментарий к доходу:", build_income_comment_keyboard())
                return
            send_message(chat_id, "Введите сумму дохода (положительное число).", build_cancel_keyboard())
            return

        if trimmed in ("/status", "/статус", "Статус"):
            handle_status(chat_id, session)
            return
        if trimmed in ("/expense", "/расход", "Расход"):
            set_state(chat_id, "expense_amount", "0", {})
            send_message(chat_id, "Введите сумму расхода:", build_cancel_keyboard())
            return
        if trimmed in ("/income", "/доход", "Доход"):
            set_state(chat_id, "income_amount", "0", {})
            send_message(chat_id, "Введите сумму дохода:", build_cancel_keyboard())
            return
        if trimmed == "/start":
            send_message(chat_id, "Добро пожаловать! Выберите действие:", build_main_menu_keyboard())
            return
        if trimmed in ("/help", "/помощь", "Справка", ""):
            send_message(chat_id, "Выберите действие:", build_main_menu_keyboard())
            return

        if state:
            clear_state(chat_id)
        send_message(chat_id, "Выберите действие:", build_main_menu_keyboard())
    finally:
        session.close()


def handle_callback_query(chat_id: int, callback_query_id: str, data: str, message_id: int | None = None):
    answer_callback_query(callback_query_id)

    session = get_session()
    try:
        if data == "cmd_status":
            handle_status(chat_id, session)
            return
        if data == "cmd_expense":
            set_state(chat_id, "expense_amount", "0", {})
            send_message(chat_id, "Введите сумму расхода:", build_cancel_keyboard())
            return
        if data == "cmd_income":
            set_state(chat_id, "income_amount", "0", {})
            send_message(chat_id, "Введите сумму дохода:", build_cancel_keyboard())
            return
        if data == "cmd_help":
            handle_help(chat_id)
            return
        if data == "cmd_cancel":
            clear_state(chat_id)
            send_message(chat_id, "Отменено. Выберите действие:", build_main_menu_keyboard())
            return

        if data == "main_full":
            hour_rate = calc_hour_rate_snapshot_for_date(calc_today(), session)
            add_work_log(session, calc_today(), JOB_MAIN, 8, STATUS_WORK, hour_rate)
            send_message(chat_id, "Записано: полный день (8 ч).")
            return
        if data == "main_none":
            send_message(chat_id, "Ок, не работал.")
            return
        if data == "main_partial":
            set_state(chat_id, "main_hours", "0", {"date": calc_today(), "weekend": False})
            send_message(chat_id, "Часы или выберите:", build_hours_quick_keyboard())
            return
        if data == "main_weekend":
            set_state(chat_id, "main_hours", "0", {"date": calc_today(), "weekend": True})
            send_message(chat_id, "Часы в выходной или выберите:", build_hours_quick_keyboard())
            return
        if data == "main_sick":
            add_work_log(session, calc_today(), JOB_MAIN, 0, STATUS_SICK, 0)
            send_message(chat_id, "Записан день больничного (первые 3 дня оплачиваются, с 4-го — нет).")
            return

        if data == "second_add":
            yesterday = calc_yesterday()
            set_state(chat_id, "second_order", "description", {"date": yesterday, "items": []})
            send_message(chat_id, "Введите описание заказа (что сделано):")
            return
        if data == "second_none":
            add_order(session, calc_yesterday(), "Нет доходов", 0)
            send_message(chat_id, "Ок, доходов нет.")
            return
        if data == "second_status":
            handle_second_job_status(chat_id, session)
            return

        if data in ("yes", "no"):
            st = get_state(chat_id)
            if st and st.get("scenario") == "second_order" and st.get("step") == "more":
                if data == "no":
                    add_order_with_items(session, st["payload"]["date"], st["payload"].get("items", []))
                    clear_state(chat_id)
                    send_message(chat_id, "Заказ сохранён.")
                else:
                    set_state(chat_id, "second_order", "description", {
                        "date": st["payload"]["date"],
                        "items": st["payload"].get("items", []),
                    })
                    send_message(chat_id, "Введите описание следующей позиции:")
            return

        if data.startswith("exp_cat_"):
            idx = int(data.replace("exp_cat_", ""))
            cat = EXPENSE_CATEGORIES[idx]
            s = get_state(chat_id)
            if s and s.get("scenario") == "expense_cat" and s.get("payload", {}).get("amount") is not None:
                set_state(chat_id, "expense_comment", "0", {"amount": s["payload"]["amount"], "category": cat})
                send_message(chat_id, "Комментарий к расходу:", build_expense_comment_keyboard())
            return

        if data == "exp_skip":
            s = get_state(chat_id)
            if s and s.get("scenario") == "expense_comment":
                add_finance_entry(session, calc_today(), TYPE_EXPENSE, s["payload"]["amount"], s["payload"]["category"], "")
                clear_state(chat_id)
                send_message(chat_id, f"Расход записан: {s['payload']['amount']} руб., {s['payload']['category']}.")
            return

        if data == "inc_skip":
            s = get_state(chat_id)
            if s and s.get("scenario") == "income_comment":
                add_finance_entry(session, calc_today(), TYPE_INCOME_SECOND, s["payload"]["amount"], "Прочее", "")
                clear_state(chat_id)
                send_message(chat_id, f"Доход записан: {s['payload']['amount']} руб.")
            return

        if data.startswith("hours_"):
            try:
                hrs = int(data.replace("hours_", ""))
            except ValueError:
                return
            if 0 <= hrs <= 24:
                s = get_state(chat_id)
                if s and s.get("scenario") == "main_hours":
                    date_str = s["payload"].get("date") or calc_today()
                    is_weekend = s["payload"].get("weekend") is True
                    status = STATUS_WEEKEND_WORK if is_weekend else STATUS_WORK
                    hour_rate = calc_hour_rate_snapshot_for_date(date_str, session)
                    add_work_log(session, date_str, JOB_MAIN, hrs, status, hour_rate)
                    clear_state(chat_id)
                    send_message(chat_id, f"Записано: {hrs} ч.")
    finally:
        session.close()


def handle_help(chat_id: int):
    msg = "Статус — ЗП, вторая работа, остаток бюджета\nРасход — записать расход\nДоход — записать внезарплатный доход"
    send_message(chat_id, msg, build_main_menu_keyboard())


def handle_status(chat_id: int, session):
    try:
        today = calc_today()
        acc = get_accrued_summary_for_payday(session)
        next_pay = get_next_pay_date(today, session)
        balance = get_budget_balance(session)
        start_month = today[:7] + "-01"
        second_month = get_accrued_second_for_period(start_month, today, session)
        log_info(session, f"handleStatus: period={acc['periodStart']}-{acc['periodEnd']} main={acc['accruedMain']} second={acc['accruedSecond']} balance={balance}")
        msg = (
            f"Накоплено ЗП (основная) с последней выплаты: {int(acc['accruedMain'])} руб.\n"
            f"Накоплено по второй работе за месяц: {int(second_month)} руб.\n"
            f"Остаток бюджета (доходы − расходы): {int(balance)} руб.\n"
            f"Следующая выплата: {next_pay}."
        )
        send_message(chat_id, msg, build_status_keyboard())
    except Exception as e:
        log_error(session, f"handleStatus: {e}")
        send_message(chat_id, "Ошибка при расчёте. Проверьте данные в таблице.")


def handle_second_job_status(chat_id: int, session):
    yesterday = calc_yesterday()
    orders = get_orders_for_period(session, yesterday, yesterday)
    total = sum(o.amount for o in orders)
    msg = f"За вчера ({yesterday}): заказов {len(orders)}, сумма {int(total)} руб."
    send_message(chat_id, msg)
