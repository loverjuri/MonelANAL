"""Slim bot handlers: status, quick expense, WorkLog/SecondJob prompt responses, payday."""
from db.repositories import (
    get_session,
    add_work_log,
    add_order,
    add_order_with_items,
    add_finance_entry,
    record_payday_received,
    get_orders_for_period,
    get_debt_summary,
    increment_category_usage,
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
from services.budget import check_category_overspend
from bot.keyboards import (
    build_main_menu_keyboard,
    build_main_work_keyboard,
    build_second_job_keyboard,
    build_expense_categories_keyboard,
    build_expense_comment_keyboard,
    build_yes_no_keyboard,
    build_hours_quick_keyboard,
    build_cancel_keyboard,
    build_status_keyboard,
    build_confirm_keyboard,
    EXPENSE_CATEGORIES,
    _inline_keyboard,
    _btn,
    _web_app_btn,
    _get_web_url,
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


def _parse_quick_expense(text: str) -> dict | None:
    t = (text or "").strip()
    if not t:
        return None
    parts = t.split()
    if t.startswith("/расход "):
        parts = parts[1:]
    if len(parts) < 2:
        return None
    try:
        amount = float(parts[0].replace(",", ".").replace(" ", ""))
    except ValueError:
        return None
    if amount <= 0:
        return None
    cat_input = " ".join(parts[1:]).strip().lower()
    if not cat_input:
        return None
    for cat in EXPENSE_CATEGORIES:
        if cat.lower().startswith(cat_input) or cat_input in cat.lower():
            return {"amount": amount, "category": cat}
    return {"amount": amount, "category": "Прочее"}


def _handle_quick_expense(chat_id: int, session, quick_add: dict):
    amount = quick_add["amount"]
    category = quick_add["category"]
    overspend = check_category_overspend(session, category, amount)
    add_finance_entry(session, calc_today(), TYPE_EXPENSE, amount, category, "")
    increment_category_usage(session, category)
    msg = f"Расход записан: {amount} руб., {category}."
    if overspend:
        msg += f"\n⚠ Перерасход по {category}: лимит {int(overspend['limit'])}, потрачено {int(overspend['after'])} (+{int(overspend['over'])})"
    send_message(chat_id, msg, build_main_menu_keyboard())


def _check_and_notify_achievements(chat_id: int, session):
    try:
        from services.gamification import check_achievements, ACHIEVEMENTS
        new = check_achievements(session)
        for code in new:
            info = ACHIEVEMENTS.get(code, {})
            send_message(chat_id, f"Достижение: {info.get('name', code)} — {info.get('desc', '')}")
    except Exception:
        pass


def _send_open_app_hint(chat_id: int, path: str = ""):
    url = _get_web_url()
    if url:
        base = url.rstrip("/").rsplit("/", 1)[0]
        target = base + "/" + path.lstrip("/") if path else url
        send_message(chat_id, "Подробнее — в приложении:", _inline_keyboard([[_web_app_btn("Открыть приложение", target)]]))


def is_exit_command(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in (
        "/start", "/help", "/помощь", "справка", "отмена", "/cancel",
        "статус", "расход", "доход",
    ) or t.startswith("/расход ")


# ─── handle_message ───────────────────────────────────────────
def handle_message(chat_id: int, text: str, message_id: int | None = None, message: dict | None = None):
    session = get_session()
    try:
        trimmed = (text or "").strip()
        log_info(session, f"handleMessage: chatId={chat_id} text={trimmed[:60]}")

        # Quick expense: /расход 500 еда
        if trimmed.startswith("/расход "):
            quick_add = _parse_quick_expense(trimmed)
            if quick_add:
                _handle_quick_expense(chat_id, session, quick_add)
                _check_and_notify_achievements(chat_id, session)
            else:
                send_message(chat_id, "Формат: /расход 500 еда", build_main_menu_keyboard())
            return

        # Check active FSM state
        state = get_state(chat_id)
        if state:
            if is_exit_command(trimmed):
                clear_state(chat_id)
                send_message(chat_id, "Выберите действие:", build_main_menu_keyboard())
                return
            scenario = state.get("scenario", "")
            if scenario == "main_hours":
                _fsm_main_hours(chat_id, session, state, trimmed)
                return
            if scenario == "second_order":
                _fsm_second_order(chat_id, session, state, trimmed)
                return
            if scenario == "payday_amount":
                _fsm_payday_amount(chat_id, session, state, trimmed)
                return
            if scenario == "expense_amount":
                _fsm_expense_amount(chat_id, session, state, trimmed)
                return
            if scenario == "expense_comment":
                _fsm_expense_comment(chat_id, session, state, trimmed)
                return
            if scenario == "confirm_large_expense":
                return

        # Text commands
        lower = trimmed.lower()
        if lower in ("/start", "/help", "/помощь", "справка", "помощь"):
            handle_help(chat_id)
            return
        if lower in ("/status", "/статус", "статус"):
            handle_status(chat_id, session)
            return
        if lower == "расход":
            set_state(chat_id, "expense_amount", "0", {})
            send_message(chat_id, "Введите сумму расхода:", build_cancel_keyboard())
            return

        # Try as quick expense: "500 еда"
        quick_add = _parse_quick_expense(trimmed)
        if quick_add:
            _handle_quick_expense(chat_id, session, quick_add)
            _check_and_notify_achievements(chat_id, session)
            return

        send_message(chat_id, "Выберите действие:", build_main_menu_keyboard())
    except Exception as e:
        log_error(session, f"handleMessage: {e}")
    finally:
        session.close()


# ─── FSM: main hours ──────────────────────────────────────────
def _fsm_main_hours(chat_id, session, state, trimmed):
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
        send_message(chat_id, f"Записано: {hours} ч.", build_main_menu_keyboard())
        return
    send_message(chat_id, "Введите число часов от 0 до 24.")


# ─── FSM: second order ────────────────────────────────────────
def _fsm_second_order(chat_id, session, state, trimmed):
    step = state.get("step", "")
    if step == "description":
        set_state(chat_id, "second_order", "amount", {
            "date": state["payload"].get("date"), "description": trimmed,
        })
        send_message(chat_id, "Введите сумму заказа (число):")
        return
    if step == "amount":
        try:
            amount = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            amount = float("nan")
        if not (amount != amount) and amount >= 0:
            desc = state["payload"].get("description", "")
            items = state["payload"].get("items") or []
            items.append({"description": desc, "amount": amount})
            set_state(chat_id, "second_order", "more", {"date": state["payload"]["date"], "items": items})
            send_message(chat_id, "Ещё позиции в этот заказ?", build_yes_no_keyboard())
            return
        send_message(chat_id, "Введите число (сумма).")
        return
    if step == "more" and trimmed.lower() in ("да", "нет"):
        if trimmed.lower() == "нет":
            add_order_with_items(session, state["payload"]["date"], state["payload"].get("items", []))
            clear_state(chat_id)
            send_message(chat_id, "Заказ сохранён.", build_main_menu_keyboard())
        else:
            set_state(chat_id, "second_order", "description", {
                "date": state["payload"]["date"], "items": state["payload"].get("items", []),
            })
            send_message(chat_id, "Введите описание следующей позиции:")


# ─── FSM: payday ──────────────────────────────────────────────
def _fsm_payday_amount(chat_id, session, state, trimmed):
    try:
        received = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        received = float("nan")
    if not (received != received) and received >= 0:
        acc = state["payload"].get("accrued") or {}
        record_payday_received(
            session, calc_today(), received, acc.get("main", 0), acc.get("second", 0),
            state["payload"].get("periodStart", ""), state["payload"].get("periodEnd", ""),
        )
        clear_state(chat_id)
        try:
            from services.goals import process_auto_fund
            funded = process_auto_fund(session, received)
            if funded:
                lines = ["Автопополнение целей:"]
                for f in funded:
                    lines.append(f"  {f['name']}: +{int(f['amount'])} руб.")
                send_message(chat_id, "\n".join(lines))
        except Exception:
            pass
        send_message(chat_id, f"Сумма {received} руб. записана.", build_main_menu_keyboard())
        return
    send_message(chat_id, "Введите положительное число.")


# ─── FSM: expense ─────────────────────────────────────────────
def _fsm_expense_amount(chat_id, session, state, trimmed):
    try:
        amount = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        amount = float("nan")
    if not (amount != amount) and amount > 0:
        threshold = 10000
        try:
            from db.repositories import get_config_param
            v = get_config_param(session, "LargeExpenseThreshold")
            if v:
                threshold = float(v)
        except Exception:
            pass
        if amount >= threshold:
            set_state(chat_id, "confirm_large_expense", "0", {"amount": amount})
            send_message(chat_id, f"Крупный расход: {amount} руб. Подтвердить?", build_confirm_keyboard())
            return
        set_state(chat_id, "expense_amount", "category", {"amount": amount, "custom_date": state.get("payload", {}).get("custom_date")})
        send_message(chat_id, "Категория:", build_expense_categories_keyboard())
        return
    send_message(chat_id, "Введите положительное число.", build_cancel_keyboard())


def _fsm_expense_comment(chat_id, session, state, trimmed):
    amount = state["payload"].get("amount", 0)
    category = state["payload"].get("category", "Прочее")
    date_str = state["payload"].get("custom_date") or calc_today()
    overspend = check_category_overspend(session, category, amount)
    add_finance_entry(session, date_str, TYPE_EXPENSE, amount, category, trimmed)
    increment_category_usage(session, category)
    clear_state(chat_id)
    msg = f"Расход записан: {amount} руб., {category}."
    if trimmed:
        msg += f" ({trimmed})"
    if overspend:
        msg += f"\n⚠ Перерасход по {category}: лимит {int(overspend['limit'])}, потрачено {int(overspend['after'])} (+{int(overspend['over'])})"
    _check_and_notify_achievements(chat_id, session)
    send_message(chat_id, msg, build_main_menu_keyboard())


# ─── handle_callback_query ─────────────────────────────────────
def handle_callback_query(chat_id: int, callback_query_id: str, data: str, message_id: int | None = None):
    answer_callback_query(callback_query_id)
    session = get_session()
    try:
        log_info(session, f"callback: chatId={chat_id} cb:{data}")
        _dispatch_callback(chat_id, data, session)
    except Exception as e:
        log_error(session, f"callback error: {e}")
    finally:
        session.close()


def _dispatch_callback(chat_id: int, data: str, session):
    # Status
    if data == "cmd_status":
        handle_status(chat_id, session)
        return

    # Expense
    if data == "cmd_expense":
        set_state(chat_id, "expense_amount", "0", {})
        send_message(chat_id, "Введите сумму расхода:", build_cancel_keyboard())
        return

    if data == "cmd_cancel":
        clear_state(chat_id)
        send_message(chat_id, "Отменено.", build_main_menu_keyboard())
        return

    # WorkLog quick buttons
    if data == "main_full":
        hour_rate = calc_hour_rate_snapshot_for_date(calc_today(), session)
        add_work_log(session, calc_today(), JOB_MAIN, 8, STATUS_WORK, hour_rate)
        send_message(chat_id, "Записано: полный день (8 ч).", build_main_menu_keyboard())
        return
    if data == "main_none":
        send_message(chat_id, "Ок, не работал.", build_main_menu_keyboard())
        return
    if data == "main_partial":
        set_state(chat_id, "main_hours", "0", {"date": calc_today(), "weekend": False})
        send_message(chat_id, "Часы:", build_hours_quick_keyboard())
        return
    if data == "main_weekend":
        set_state(chat_id, "main_hours", "0", {"date": calc_today(), "weekend": True})
        send_message(chat_id, "Часы в выходной:", build_hours_quick_keyboard())
        return
    if data == "main_sick":
        add_work_log(session, calc_today(), JOB_MAIN, 0, STATUS_SICK, 0)
        send_message(chat_id, "Записан день больничного.", build_main_menu_keyboard())
        return
    if data.startswith("hours_"):
        hrs = int(data.replace("hours_", ""))
        st = get_state(chat_id)
        if st and st.get("scenario") == "main_hours":
            date_str = st["payload"].get("date") or calc_today()
            is_weekend = st["payload"].get("weekend") is True
            status = STATUS_WEEKEND_WORK if is_weekend else STATUS_WORK
            hour_rate = calc_hour_rate_snapshot_for_date(date_str, session)
            add_work_log(session, date_str, JOB_MAIN, hrs, status, hour_rate)
            clear_state(chat_id)
            send_message(chat_id, f"Записано: {hrs} ч.", build_main_menu_keyboard())
        return

    # Second job quick buttons
    if data == "second_add":
        set_state(chat_id, "second_order", "description", {"date": calc_yesterday(), "items": []})
        send_message(chat_id, "Описание заказа:", build_cancel_keyboard())
        return
    if data == "second_none":
        add_order(session, calc_yesterday(), "Нет доходов", 0)
        send_message(chat_id, "Записано.", build_main_menu_keyboard())
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
                send_message(chat_id, "Заказ сохранён.", build_main_menu_keyboard())
            else:
                set_state(chat_id, "second_order", "description", {
                    "date": st["payload"]["date"], "items": st["payload"].get("items", []),
                })
                send_message(chat_id, "Описание следующей позиции:", build_cancel_keyboard())
        return

    # Expense category selection
    if data.startswith("exp_cat_"):
        idx = int(data.replace("exp_cat_", ""))
        cat = EXPENSE_CATEGORIES[idx] if idx < len(EXPENSE_CATEGORIES) else "Прочее"
        s = get_state(chat_id)
        if s and s.get("scenario") == "expense_amount":
            p = s.get("payload", {})
            p["category"] = cat
            set_state(chat_id, "expense_comment", "0", p)
            send_message(chat_id, f"Категория: {cat}. Комментарий (или пропустите):", build_expense_comment_keyboard())
        return
    if data == "exp_skip":
        s = get_state(chat_id)
        if s and s.get("scenario") == "expense_comment":
            _fsm_expense_comment(chat_id, session, s, "")
        return

    # Confirm large expense
    if data == "confirm_yes":
        st = get_state(chat_id)
        if st and st.get("scenario") == "confirm_large_expense":
            amount = st["payload"].get("amount", 0)
            set_state(chat_id, "expense_amount", "category", {"amount": amount})
            send_message(chat_id, "Категория:", build_expense_categories_keyboard())
        return
    if data == "confirm_no":
        clear_state(chat_id)
        send_message(chat_id, "Расход отменён.", build_main_menu_keyboard())
        return

    # Catch-all: suggest opening web app
    url = _get_web_url()
    if url:
        send_message(chat_id, "Эта функция доступна в приложении:", _inline_keyboard([[_web_app_btn("Открыть приложение", url)]]))
    else:
        send_message(chat_id, "Выберите действие:", build_main_menu_keyboard())


# ─── Status and help ──────────────────────────────────────────
def handle_help(chat_id: int):
    url = _get_web_url()
    msg = (
        "Статус — ЗП, бюджет\n"
        "Расход — записать расход (или /расход 500 еда)\n\n"
        "Всё остальное — в веб-приложении:\n"
        "бюджет, цели, долги, подписки, аналитика, история, настройки"
    )
    rows = [[_btn("Статус", "cmd_status"), _btn("Расход", "cmd_expense")]]
    if url:
        rows.append([_web_app_btn("Открыть приложение", url)])
    send_message(chat_id, msg, _inline_keyboard(rows))


def handle_status(chat_id: int, session):
    try:
        today = calc_today()
        acc = get_accrued_summary_for_payday(session)
        next_pay = get_next_pay_date(today, session)
        balance = get_budget_balance(session)
        start_month = today[:7] + "-01"
        second_month = get_accrued_second_for_period(start_month, today, session)
        debt_sum = get_debt_summary(session)
        msg = (
            f"Накоплено ЗП: {int(acc['accruedMain'])} руб.\n"
            f"Вторая работа (месяц): {int(second_month)} руб.\n"
            f"Баланс: {int(balance)} руб.\n"
            f"Следующая выплата: {next_pay}\n"
            f"Долги: я должен {int(debt_sum['owe'])}, мне должны {int(debt_sum['lent'])}"
        )
        send_message(chat_id, msg, build_status_keyboard())
    except Exception as e:
        log_error(session, f"handleStatus: {e}")
        send_message(chat_id, "Ошибка при расчёте.")


def handle_second_job_status(chat_id: int, session):
    yesterday = calc_yesterday()
    orders = get_orders_for_period(session, yesterday, yesterday)
    total = sum(o.amount for o in orders)
    send_message(chat_id, f"За вчера ({yesterday}): заказов {len(orders)}, сумма {int(total)} руб.", build_second_job_keyboard())
