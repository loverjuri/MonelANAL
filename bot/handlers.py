"""Message and callback handlers. FSM logic for all features."""
from db.repositories import (
    get_session,
    add_work_log,
    add_order,
    add_order_with_items,
    add_finance_entry,
    record_payday_received,
    get_orders_for_period,
    get_budget_limits_map,
    set_budget_plan_limit,
    get_active_goals,
    add_goal,
    update_goal_current,
    get_goal,
    get_active_subscriptions,
    add_subscription,
    get_subscriptions_due_soon,
    get_last_finance_entry,
    get_finance_by_id,
    update_finance_entry,
    delete_finance_entry,
    get_finance_for_period,
    log_info,
    log_error,
    # Phase 1: Debts
    add_debt,
    get_active_debts,
    get_debt,
    add_debt_payment,
    get_debt_payments,
    get_debt_summary,
    # Phase 2: Categories
    get_top_categories,
    increment_category_usage,
    add_category,
    seed_system_categories,
    # Phase 5: Subscriptions ext
    get_overdue_subscriptions,
    # Phase 8: UX
    get_finance_history,
    search_finance,
    get_templates,
    add_template,
    use_template,
    # Phase 4: Goals ext
    archive_goal,
    get_archived_goals,
    # Phase 9: Achievements
    get_achievements,
    # Config
    get_config_param,
    set_config_param,
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
from bot.telegram_api import send_message, answer_callback_query, send_document, send_photo
from services.budget import (
    get_budget_status, get_month_range, check_category_overspend,
    suggest_plan_from_history, get_forecast_end_of_month, get_5030_20_hint,
)
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
    build_budget_keyboard,
    build_budget_categories_keyboard,
    build_goals_keyboard,
    build_goal_select_keyboard,
    build_subscriptions_keyboard,
    build_edit_last_keyboard,
    build_debts_keyboard,
    build_debt_direction_keyboard,
    build_debt_detail_keyboard,
    build_debt_select_keyboard,
    build_analytics_keyboard,
    build_period_keyboard,
    build_history_keyboard,
    build_templates_keyboard,
    build_settings_keyboard,
    build_goal_type_keyboard,
    build_confirm_keyboard,
    build_date_choice_keyboard,
    build_recent_entries_keyboard,
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
        amt_str = parts[0].replace(",", ".").replace(" ", "")
        amount = float(amt_str)
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
    _check_and_notify_achievements(chat_id, session)
    send_message(chat_id, msg, build_main_menu_keyboard())


def _check_and_notify_achievements(chat_id: int, session):
    try:
        from services.gamification import check_achievements, ACHIEVEMENTS
        new = check_achievements(session)
        for code in new:
            info = ACHIEVEMENTS.get(code, {})
            send_message(chat_id, f"🏆 Достижение: {info.get('name', code)} — {info.get('desc', '')}")
    except Exception:
        pass


def is_exit_command(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in (
        "/start", "/help", "/помощь", "справка", "отмена", "/cancel",
        "статус", "расход", "доход", "бюджет", "цели", "подписки",
        "отчёт", "экспорт", "редактировать последний", "долги",
        "аналитика", "история", "шаблоны", "настройки",
    ) or t.startswith("/расход ") or t.startswith("/редактировать")


# ─── handle_message ───────────────────────────────────────────
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

        # FSM dispatch
        scenario = state.get("scenario", "") if state else ""

        if scenario == "main_hours":
            _fsm_main_hours(chat_id, session, state, trimmed)
            return
        if scenario == "second_order":
            _fsm_second_order(chat_id, session, state, trimmed)
            return
        if scenario == "payday_amount":
            _fsm_payday_amount(chat_id, session, state, trimmed)
            return
        if scenario == "expense_comment":
            _fsm_expense_comment(chat_id, session, state, trimmed)
            return
        if scenario == "expense_amount":
            _fsm_expense_amount(chat_id, session, state, trimmed)
            return
        if scenario == "income_comment":
            _fsm_income_comment(chat_id, session, state, trimmed)
            return
        if scenario == "income_amount":
            _fsm_income_amount(chat_id, session, state, trimmed)
            return
        if scenario == "edit_expense":
            _fsm_edit_expense(chat_id, session, state, trimmed)
            return
        if scenario == "budget_set_amount":
            _fsm_budget_set_amount(chat_id, session, state, trimmed)
            return
        if scenario == "goals_add":
            _fsm_goals_add(chat_id, session, state, trimmed)
            return
        if scenario == "goals_fund_amount":
            _fsm_goals_fund(chat_id, session, state, trimmed)
            return
        if scenario == "subs_add":
            _fsm_subs_add(chat_id, session, state, trimmed)
            return
        if scenario == "debts_add":
            _fsm_debts_add(chat_id, session, state, trimmed)
            return
        if scenario == "debt_pay_amount":
            _fsm_debt_pay(chat_id, session, state, trimmed)
            return
        if scenario == "search":
            _fsm_search(chat_id, session, state, trimmed)
            return
        if scenario == "tpl_add":
            _fsm_tpl_add(chat_id, session, state, trimmed)
            return
        if scenario == "settings_quiet":
            _fsm_settings_quiet(chat_id, session, state, trimmed)
            return
        if scenario == "settings_threshold":
            _fsm_settings_threshold(chat_id, session, state, trimmed)
            return
        if scenario == "confirm_large_expense":
            _fsm_confirm_large(chat_id, session, state, trimmed)
            return
        if scenario == "delete_all_confirm":
            _fsm_delete_all(chat_id, session, state, trimmed)
            return
        if scenario == "custom_date_expense":
            _fsm_custom_date(chat_id, session, state, trimmed)
            return

        quick_add = _parse_quick_expense(trimmed)
        if quick_add and not state:
            _handle_quick_expense(chat_id, session, quick_add)
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
        if trimmed in ("/редактировать", "Редактировать", "редактировать последний"):
            _handle_edit_last_menu(chat_id, session)
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


# ─── FSM handlers ──────────────────────────────────────────────
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
        send_message(chat_id, f"Записано: {hours} ч.")
        return
    send_message(chat_id, "Введите число часов от 0 до 24.")


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
            send_message(chat_id, "Заказ сохранён.")
        else:
            set_state(chat_id, "second_order", "description", {
                "date": state["payload"]["date"], "items": state["payload"].get("items", []),
            })
            send_message(chat_id, "Введите описание следующей позиции:")


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
        # Auto-fund goals on payday
        try:
            from services.goals import process_auto_fund
            funded = process_auto_fund(session, received)
            if funded:
                lines = ["Автопополнение целей:"]
                for f in funded:
                    lines.append(f"  {f['name']}: +{int(f['amount'])} (итого {int(f['current'])}/{int(f['target'])})")
                send_message(chat_id, "\n".join(lines))
        except Exception:
            pass
        send_message(chat_id, f"Сумма {received} руб. записана.", build_main_menu_keyboard())
        return
    send_message(chat_id, "Введите число (сумма, полученная на карту).")


def _fsm_expense_comment(chat_id, session, state, trimmed):
    amount = state["payload"]["amount"]
    category = state["payload"]["category"]
    comment = "" if trimmed in ("-", "пропустить", "нет") else trimmed
    overspend = check_category_overspend(session, category, amount)
    add_finance_entry(session, calc_today(), TYPE_EXPENSE, amount, category, comment)
    increment_category_usage(session, category)
    clear_state(chat_id)
    msg = f"Расход записан: {amount} руб., {category}" + (f", {comment}" if comment else "") + "."
    if overspend:
        msg += f"\n⚠ Перерасход по {category}: лимит {int(overspend['limit'])}, потрачено {int(overspend['after'])} (+{int(overspend['over'])})"
    _check_and_notify_achievements(chat_id, session)
    send_message(chat_id, msg, build_main_menu_keyboard())


def _fsm_expense_amount(chat_id, session, state, trimmed):
    try:
        amt = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        amt = float("nan")
    if not (amt != amt) and amt > 0:
        from services.recommendations import check_large_expense
        if check_large_expense(session, amt):
            set_state(chat_id, "confirm_large_expense", "0", {"amount": amt})
            send_message(chat_id, f"⚠ Крупный расход: {int(amt)} руб. Продолжить?", build_confirm_keyboard())
            return
        set_state(chat_id, "expense_cat", "0", {"amount": amt})
        send_message(chat_id, "Выберите категорию:", build_expense_categories_keyboard())
        return
    send_message(chat_id, "Введите сумму расхода (положительное число).", build_cancel_keyboard())


def _fsm_income_comment(chat_id, session, state, trimmed):
    amount = state["payload"]["amount"]
    comment = "" if trimmed in ("-", "пропустить", "нет") else trimmed
    add_finance_entry(session, calc_today(), TYPE_INCOME_SECOND, amount, "Прочее", comment)
    clear_state(chat_id)
    send_message(chat_id, f"Доход записан: {amount} руб." + (f" ({comment})" if comment else "") + ".")


def _fsm_income_amount(chat_id, session, state, trimmed):
    try:
        amt = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        amt = float("nan")
    if not (amt != amt) and amt > 0:
        set_state(chat_id, "income_comment", "0", {"amount": amt})
        send_message(chat_id, "Комментарий к доходу:", build_income_comment_keyboard())
        return
    send_message(chat_id, "Введите сумму дохода (положительное число).", build_cancel_keyboard())


def _fsm_edit_expense(chat_id, session, state, trimmed):
    try:
        amt = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        send_message(chat_id, "Введите число:", build_cancel_keyboard())
        return
    if amt > 0:
        fid = state["payload"].get("finance_id", "")
        if update_finance_entry(session, fid, amount=amt):
            clear_state(chat_id)
            send_message(chat_id, f"Расход обновлён: {amt} руб.", build_main_menu_keyboard())
        else:
            clear_state(chat_id)
            send_message(chat_id, "Ошибка обновления.", build_main_menu_keyboard())


def _fsm_budget_set_amount(chat_id, session, state, trimmed):
    try:
        amt = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        amt = float("nan")
    if not (amt != amt) and amt >= 0:
        cat = state["payload"].get("category", "")
        month_year = state["payload"].get("month_year", calc_today()[:7])
        set_budget_plan_limit(session, month_year, cat, amt)
        clear_state(chat_id)
        send_message(chat_id, f"Лимит {cat}: {amt} руб. на {month_year}", build_main_menu_keyboard())
        return
    send_message(chat_id, "Введите число (лимит по категории):", build_cancel_keyboard())


def _fsm_goals_add(chat_id, session, state, trimmed):
    step = state.get("step", "")
    if step == "type":
        set_state(chat_id, "goals_add", "name", {**state["payload"]})
        send_message(chat_id, "Название цели:", build_cancel_keyboard())
        return
    if step == "name":
        set_state(chat_id, "goals_add", "target", {**state["payload"], "name": trimmed})
        send_message(chat_id, "Целевая сумма (руб):", build_cancel_keyboard())
        return
    if step == "target":
        try:
            tgt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if tgt > 0:
            set_state(chat_id, "goals_add", "deadline", {**state["payload"], "target": tgt})
            send_message(chat_id, "Срок (YYYY-MM-DD или '-' если без срока):", build_cancel_keyboard())
        else:
            send_message(chat_id, "Введите положительное число:", build_cancel_keyboard())
        return
    if step == "deadline":
        dl = "" if trimmed in ("-", "нет", "") else trimmed[:10]
        goal_type = state["payload"].get("goal_type", "other")
        add_goal(session, state["payload"]["name"], state["payload"]["target"], dl)
        clear_state(chat_id)
        send_message(chat_id, "Цель добавлена.", build_main_menu_keyboard())


def _fsm_goals_fund(chat_id, session, state, trimmed):
    try:
        amt = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        send_message(chat_id, "Введите число:", build_cancel_keyboard())
        return
    if amt > 0:
        gid = state["payload"].get("goal_id", "")
        if update_goal_current(session, gid, amt):
            g = get_goal(session, gid)
            msg = f"Пополнено: {amt} руб. Прогресс: {int(g.current_amount)}/{int(g.target_amount)}"
            if g.current_amount >= g.target_amount:
                msg += "\n🎉 Цель достигнута!"
            send_message(chat_id, msg, build_main_menu_keyboard())
        else:
            send_message(chat_id, "Ошибка. Цель не найдена.", build_main_menu_keyboard())
        clear_state(chat_id)


def _fsm_subs_add(chat_id, session, state, trimmed):
    step = state.get("step", "")
    if step == "name":
        set_state(chat_id, "subs_add", "amount", {"name": trimmed})
        send_message(chat_id, "Сумма (руб):", build_cancel_keyboard())
        return
    if step == "amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt > 0:
            set_state(chat_id, "subs_add", "cycle", {**state["payload"], "amount": amt})
            send_message(chat_id, "Период: месяц / неделя / год (или м/н/г):", build_cancel_keyboard())
        return
    if step == "cycle":
        c = trimmed.lower()[:1]
        cycle = "monthly" if c in ("м", "m", "1") else "weekly" if c in ("н", "w") else "yearly" if c in ("г", "y") else "monthly"
        set_state(chat_id, "subs_add", "next_date", {**state["payload"], "cycle": cycle})
        send_message(chat_id, "Дата следующего списания (YYYY-MM-DD):", build_cancel_keyboard())
        return
    if step == "next_date":
        dt = trimmed[:10]
        if len(dt) >= 10 and dt[4] == "-" and dt[7] == "-":
            add_subscription(session, state["payload"]["name"], state["payload"]["amount"], state["payload"]["cycle"], dt)
            clear_state(chat_id)
            send_message(chat_id, "Подписка добавлена.", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Неверный формат даты. Используйте YYYY-MM-DD.", build_cancel_keyboard())


def _fsm_debts_add(chat_id, session, state, trimmed):
    step = state.get("step", "")
    if step == "counterparty":
        set_state(chat_id, "debts_add", "amount", {**state["payload"], "counterparty": trimmed})
        send_message(chat_id, "Сумма долга (руб):", build_cancel_keyboard())
        return
    if step == "amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt > 0:
            set_state(chat_id, "debts_add", "interest", {**state["payload"], "amount": amt})
            send_message(chat_id, "Процентная ставка (0 если без процентов):", build_cancel_keyboard())
        return
    if step == "interest":
        try:
            rate = float(trimmed.replace(",", "."))
        except ValueError:
            rate = 0
        set_state(chat_id, "debts_add", "due_date", {**state["payload"], "interest": rate})
        send_message(chat_id, "Дата возврата (YYYY-MM-DD или '-'):", build_cancel_keyboard())
        return
    if step == "due_date":
        due = "" if trimmed in ("-", "нет", "") else trimmed[:10]
        p = state["payload"]
        add_debt(session, p.get("direction", "owe"), p["counterparty"], p["amount"], p.get("interest", 0), "fixed", 0, due)
        clear_state(chat_id)
        send_message(chat_id, "Долг добавлен.", build_main_menu_keyboard())


def _fsm_debt_pay(chat_id, session, state, trimmed):
    try:
        amt = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        send_message(chat_id, "Введите число:", build_cancel_keyboard())
        return
    if amt > 0:
        debt_id = state["payload"].get("debt_id", "")
        pid = add_debt_payment(session, debt_id, amt)
        if pid:
            debt = get_debt(session, debt_id)
            add_finance_entry(session, calc_today(), TYPE_EXPENSE, amt, "Долги", f"Погашение: {debt.counterparty if debt else ''}")
            msg = f"Платёж {int(amt)} руб."
            if debt:
                msg += f" Остаток: {int(debt.remaining_amount)} руб."
                if debt.remaining_amount <= 0:
                    msg += "\n🎉 Долг полностью погашен!"
            send_message(chat_id, msg, build_main_menu_keyboard())
        else:
            send_message(chat_id, "Ошибка: долг не найден.", build_main_menu_keyboard())
        clear_state(chat_id)


def _fsm_search(chat_id, session, state, trimmed):
    results = search_finance(session, trimmed, 10)
    if not results:
        send_message(chat_id, "Ничего не найдено.", build_main_menu_keyboard())
    else:
        lines = [f"Найдено ({len(results)}):"]
        for r in results:
            lines.append(f"  {r.date} {r.type} {int(r.amount)} {r.category or ''} {r.comment or ''}")
        send_message(chat_id, "\n".join(lines), build_main_menu_keyboard())
    clear_state(chat_id)


def _fsm_tpl_add(chat_id, session, state, trimmed):
    step = state.get("step", "")
    if step == "name":
        set_state(chat_id, "tpl_add", "amount", {"name": trimmed})
        send_message(chat_id, "Сумма шаблона (руб):", build_cancel_keyboard())
        return
    if step == "amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt > 0:
            set_state(chat_id, "tpl_add", "category", {**state["payload"], "amount": amt})
            send_message(chat_id, "Категория:", build_expense_categories_keyboard())
        return
    if step == "category":
        add_template(session, state["payload"]["name"], state["payload"]["amount"], trimmed)
        clear_state(chat_id)
        send_message(chat_id, "Шаблон добавлен.", build_main_menu_keyboard())


def _fsm_settings_quiet(chat_id, session, state, trimmed):
    parts = trimmed.replace("-", " ").replace(":", " ").split()
    if len(parts) >= 2:
        try:
            h_start = int(parts[0])
            h_end = int(parts[1])
            if 0 <= h_start <= 23 and 0 <= h_end <= 23:
                set_config_param(session, "QuietHoursStart", str(h_start))
                set_config_param(session, "QuietHoursEnd", str(h_end))
                clear_state(chat_id)
                send_message(chat_id, f"Тихие часы: {h_start}:00 — {h_end}:00", build_settings_keyboard())
                return
        except ValueError:
            pass
    send_message(chat_id, "Введите два числа (начало конец), например: 23 7", build_cancel_keyboard())


def _fsm_settings_threshold(chat_id, session, state, trimmed):
    try:
        val = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        send_message(chat_id, "Введите число:", build_cancel_keyboard())
        return
    if val > 0:
        set_config_param(session, "LargeExpenseThreshold", str(int(val)))
        clear_state(chat_id)
        send_message(chat_id, f"Порог крупного расхода: {int(val)} руб.", build_settings_keyboard())


def _fsm_confirm_large(chat_id, session, state, trimmed):
    t = trimmed.lower()
    if t in ("да", "yes"):
        amt = state["payload"]["amount"]
        set_state(chat_id, "expense_cat", "0", {"amount": amt})
        send_message(chat_id, "Выберите категорию:", build_expense_categories_keyboard())
    else:
        clear_state(chat_id)
        send_message(chat_id, "Расход отменён.", build_main_menu_keyboard())


def _fsm_delete_all(chat_id, session, state, trimmed):
    if trimmed == "УДАЛИТЬ":
        from services.backup import delete_all_data
        delete_all_data(session)
        clear_state(chat_id)
        send_message(chat_id, "Все данные удалены.", build_main_menu_keyboard())
    else:
        clear_state(chat_id)
        send_message(chat_id, "Удаление отменено.", build_settings_keyboard())


def _fsm_custom_date(chat_id, session, state, trimmed):
    dt = trimmed[:10]
    if len(dt) >= 10 and dt[4] == "-" and dt[7] == "-":
        set_state(chat_id, "expense_amount", "0", {"custom_date": dt})
        send_message(chat_id, f"Дата: {dt}. Введите сумму расхода:", build_cancel_keyboard())
    else:
        send_message(chat_id, "Неверный формат. Используйте YYYY-MM-DD.", build_cancel_keyboard())


# ─── handle_callback_query ─────────────────────────────────────
def handle_callback_query(chat_id: int, callback_query_id: str, data: str, message_id: int | None = None):
    answer_callback_query(callback_query_id)
    session = get_session()
    try:
        _dispatch_callback(chat_id, data, session)
    finally:
        session.close()


def _dispatch_callback(chat_id: int, data: str, session):
    # Navigation
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
    if data == "cmd_budget":
        send_message(chat_id, "Бюджет: план и факт по категориям.", build_budget_keyboard())
        return
    if data == "cmd_goals":
        send_message(chat_id, "Цели накоплений.", build_goals_keyboard())
        return
    if data == "cmd_debts":
        send_message(chat_id, "Долги и кредиты.", build_debts_keyboard())
        return
    if data == "cmd_subscriptions":
        send_message(chat_id, "Регулярные платежи (подписки).", build_subscriptions_keyboard())
        return
    if data == "cmd_analytics":
        send_message(chat_id, "Аналитика и отчёты.", build_analytics_keyboard())
        return
    if data == "cmd_history":
        send_message(chat_id, "История операций.", build_history_keyboard())
        return
    if data == "cmd_templates":
        templates = get_templates(session)
        if templates:
            send_message(chat_id, "Шаблоны расходов:", build_templates_keyboard(templates))
        else:
            from bot.keyboards import _inline_keyboard, _btn
            send_message(chat_id, "Шаблонов нет.", _inline_keyboard([[_btn("Добавить шаблон", "tpl_add")], [_btn("Назад", "cmd_help")]]))
        return
    if data == "cmd_settings":
        send_message(chat_id, "Настройки.", build_settings_keyboard())
        return
    if data == "cmd_report":
        msg = handle_monthly_report(chat_id, session)
        send_message(chat_id, msg, build_main_menu_keyboard())
        return
    if data == "cmd_edit_last":
        _handle_edit_last_menu(chat_id, session)
        return
    if data == "cmd_export":
        _handle_export(chat_id, session)
        return
    if data == "cmd_cancel":
        clear_state(chat_id)
        send_message(chat_id, "Отменено. Выберите действие:", build_main_menu_keyboard())
        return

    # Work
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
        send_message(chat_id, "Часы в выходной:", build_hours_quick_keyboard())
        return
    if data == "main_sick":
        add_work_log(session, calc_today(), JOB_MAIN, 0, STATUS_SICK, 0)
        send_message(chat_id, "Записан день больничного.")
        return

    # Second job
    if data == "second_add":
        set_state(chat_id, "second_order", "description", {"date": calc_yesterday(), "items": []})
        send_message(chat_id, "Описание заказа:")
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
                    "date": st["payload"]["date"], "items": st["payload"].get("items", []),
                })
                send_message(chat_id, "Описание следующей позиции:")
        return

    # Confirm large expense
    if data == "confirm_yes":
        st = get_state(chat_id)
        if st and st.get("scenario") == "confirm_large_expense":
            amt = st["payload"]["amount"]
            set_state(chat_id, "expense_cat", "0", {"amount": amt})
            send_message(chat_id, "Выберите категорию:", build_expense_categories_keyboard())
        return
    if data == "confirm_no":
        clear_state(chat_id)
        send_message(chat_id, "Расход отменён.", build_main_menu_keyboard())
        return

    # Budget
    if data == "budget_set":
        month_year = calc_today()[:7]
        send_message(chat_id, f"Категория для лимита ({month_year}):", build_budget_categories_keyboard(month_year))
        return
    if data == "budget_status":
        _handle_budget_status(chat_id, session)
        return
    if data == "budget_suggest":
        _handle_budget_suggest(chat_id, session)
        return
    if data == "budget_forecast":
        _handle_budget_forecast(chat_id, session)
        return
    if data.startswith("budget_cat_"):
        rest = data.replace("budget_cat_", "")
        parts = rest.split("_", 1)
        if len(parts) >= 2:
            idx_str, month_year = parts[0], parts[1].replace("_", "-")
            try:
                idx = int(idx_str)
                if 0 <= idx < len(EXPENSE_CATEGORIES):
                    cat = EXPENSE_CATEGORIES[idx]
                    set_state(chat_id, "budget_set_amount", "0", {"category": cat, "month_year": month_year})
                    send_message(chat_id, f"Лимит для «{cat}» на {month_year} (руб):", build_cancel_keyboard())
            except ValueError:
                pass
        return

    # Goals
    if data == "goals_list":
        _handle_goals_list(chat_id, session)
        return
    if data == "goals_add":
        set_state(chat_id, "goals_add", "type", {})
        send_message(chat_id, "Тип цели:", build_goal_type_keyboard())
        return
    if data.startswith("gtype_"):
        goal_type = data.replace("gtype_", "")
        set_state(chat_id, "goals_add", "name", {"goal_type": goal_type})
        send_message(chat_id, "Название цели:", build_cancel_keyboard())
        return
    if data == "goals_fund":
        goals = get_active_goals(session)
        if not goals:
            send_message(chat_id, "Нет активных целей.", build_goals_keyboard())
            return
        send_message(chat_id, "Выберите цель:", build_goal_select_keyboard(goals))
        return
    if data == "goals_archived":
        archived = get_archived_goals(session)
        if not archived:
            send_message(chat_id, "Архив пуст.", build_goals_keyboard())
            return
        lines = ["Архив целей:"]
        for g in archived:
            lines.append(f"  {g.name}: {int(g.current_amount)}/{int(g.target_amount)}")
        send_message(chat_id, "\n".join(lines), build_goals_keyboard())
        return
    if data.startswith("goal_fund_"):
        gid = data.replace("goal_fund_", "")
        if get_goal(session, gid):
            set_state(chat_id, "goals_fund_amount", "0", {"goal_id": gid})
            send_message(chat_id, "Сумма пополнения (руб):", build_cancel_keyboard())
        return
    if data.startswith("goal_archive_"):
        gid = data.replace("goal_archive_", "")
        archive_goal(session, gid)
        send_message(chat_id, "Цель архивирована.", build_goals_keyboard())
        return

    # Debts
    if data == "debts_list":
        _handle_debts_list(chat_id, session)
        return
    if data == "debts_add":
        send_message(chat_id, "Кто должен?", build_debt_direction_keyboard())
        return
    if data in ("debt_dir_owe", "debt_dir_lent"):
        direction = "owe" if data == "debt_dir_owe" else "lent"
        set_state(chat_id, "debts_add", "counterparty", {"direction": direction})
        send_message(chat_id, "Имя контрагента:", build_cancel_keyboard())
        return
    if data.startswith("debt_detail_"):
        debt_id = data.replace("debt_detail_", "")
        debt = get_debt(session, debt_id)
        if debt:
            d_label = "Я должен" if debt.direction == "owe" else "Мне должны"
            msg = (
                f"{d_label}: {debt.counterparty}\n"
                f"Сумма: {int(debt.original_amount)} руб.\n"
                f"Остаток: {int(debt.remaining_amount)} руб.\n"
                f"Ставка: {debt.interest_rate}%\n"
                f"Срок: {debt.due_date or 'не указан'}"
            )
            send_message(chat_id, msg, build_debt_detail_keyboard(debt_id))
        return
    if data.startswith("debt_pay_"):
        debt_id = data.replace("debt_pay_", "")
        set_state(chat_id, "debt_pay_amount", "0", {"debt_id": debt_id})
        send_message(chat_id, "Сумма платежа (руб):", build_cancel_keyboard())
        return
    if data.startswith("debt_history_"):
        debt_id = data.replace("debt_history_", "")
        payments = get_debt_payments(session, debt_id)
        if not payments:
            send_message(chat_id, "Платежей нет.", build_debts_keyboard())
            return
        lines = ["История платежей:"]
        for p in payments:
            lines.append(f"  {p.date}: {int(p.amount)} руб. {p.comment or ''}")
        send_message(chat_id, "\n".join(lines), build_debts_keyboard())
        return

    # Subscriptions
    if data == "subs_list":
        _handle_subs_list(chat_id, session)
        return
    if data == "subs_add":
        set_state(chat_id, "subs_add", "name", {})
        send_message(chat_id, "Название подписки:", build_cancel_keyboard())
        return
    if data == "subs_overdue":
        overdue = get_overdue_subscriptions(session)
        if not overdue:
            send_message(chat_id, "Просроченных подписок нет.", build_subscriptions_keyboard())
        else:
            lines = ["Просроченные:"]
            for s in overdue:
                lines.append(f"  • {s.name}: {int(s.amount)} руб., дата была {s.next_date}")
            send_message(chat_id, "\n".join(lines), build_subscriptions_keyboard())
        return

    # Edit/delete
    if data == "edit_last_expense":
        last = get_last_finance_entry(session, "Expense", 1)
        if not last:
            send_message(chat_id, "Нет расходов.", build_main_menu_keyboard())
            return
        r = last[0]
        set_state(chat_id, "edit_expense", "amount", {"finance_id": r.id, "prev_amount": r.amount})
        send_message(chat_id, f"Новая сумма (было {r.amount}):", build_cancel_keyboard())
        return
    if data == "delete_last_expense":
        last = get_last_finance_entry(session, "Expense", 1)
        if not last:
            send_message(chat_id, "Нет расходов.", build_main_menu_keyboard())
            return
        delete_finance_entry(session, last[0].id)
        send_message(chat_id, "Последний расход удалён.", build_main_menu_keyboard())
        return
    if data.startswith("edit_entry_"):
        fid = data.replace("edit_entry_", "")
        entry = get_finance_by_id(session, fid)
        if entry:
            set_state(chat_id, "edit_expense", "amount", {"finance_id": fid, "prev_amount": entry.amount})
            send_message(chat_id, f"Новая сумма (было {entry.amount}):", build_cancel_keyboard())
        return

    # Expense category selection
    if data.startswith("exp_cat_"):
        idx = int(data.replace("exp_cat_", ""))
        cat = EXPENSE_CATEGORIES[idx]
        s = get_state(chat_id)
        if s and s.get("scenario") == "expense_cat" and s.get("payload", {}).get("amount") is not None:
            set_state(chat_id, "expense_comment", "0", {"amount": s["payload"]["amount"], "category": cat})
            send_message(chat_id, "Комментарий к расходу:", build_expense_comment_keyboard())
        elif s and s.get("scenario") == "tpl_add" and s.get("step") == "category":
            add_template(session, s["payload"]["name"], s["payload"]["amount"], cat)
            clear_state(chat_id)
            send_message(chat_id, "Шаблон добавлен.", build_main_menu_keyboard())
        return
    if data == "exp_skip":
        s = get_state(chat_id)
        if s and s.get("scenario") == "expense_comment":
            amount = s["payload"]["amount"]
            category = s["payload"]["category"]
            overspend = check_category_overspend(session, category, amount)
            add_finance_entry(session, calc_today(), TYPE_EXPENSE, amount, category, "")
            increment_category_usage(session, category)
            clear_state(chat_id)
            msg = f"Расход записан: {amount} руб., {category}."
            if overspend:
                msg += f"\n⚠ Перерасход по {category}: лимит {int(overspend['limit'])}, потрачено {int(overspend['after'])} (+{int(overspend['over'])})"
            _check_and_notify_achievements(chat_id, session)
            send_message(chat_id, msg)
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
        return

    # Analytics
    if data == "analytics_period":
        send_message(chat_id, "Выберите период:", build_period_keyboard("report"))
        return
    if data.startswith("report_"):
        period_type = data.replace("report_", "")
        from services.reports import generate_period_report
        msg = generate_period_report(session, period_type)
        send_message(chat_id, msg, build_analytics_keyboard())
        return
    if data == "analytics_chart":
        _handle_analytics_chart(chat_id, session)
        return
    if data == "analytics_top":
        _handle_analytics_top(chat_id, session)
        return
    if data == "analytics_compare":
        send_message(chat_id, "Сравнить за:", build_period_keyboard("compare"))
        return
    if data.startswith("compare_"):
        period_type = data.replace("compare_", "")
        from services.reports import compare_with_previous
        msg = compare_with_previous(session, period_type)
        send_message(chat_id, msg, build_analytics_keyboard())
        return
    if data == "analytics_daily_avg":
        from services.reports import get_daily_average, get_period_range
        start, end = get_period_range("month")
        avg = get_daily_average(session, start, end)
        send_message(chat_id, f"Средний расход/день за этот месяц: {int(avg)} руб.", build_analytics_keyboard())
        return

    # History
    if data.startswith("history_"):
        period = data.replace("history_", "")
        _handle_history(chat_id, session, period)
        return

    # Templates
    if data == "tpl_add":
        set_state(chat_id, "tpl_add", "name", {})
        send_message(chat_id, "Название шаблона:", build_cancel_keyboard())
        return
    if data.startswith("tpl_use_"):
        tpl_id = data.replace("tpl_use_", "")
        tpl = use_template(session, tpl_id)
        if tpl:
            overspend = check_category_overspend(session, tpl["category"], tpl["amount"])
            add_finance_entry(session, calc_today(), TYPE_EXPENSE, tpl["amount"], tpl["category"], f"Шаблон: {tpl['name']}")
            msg = f"Расход по шаблону: {tpl['name']} — {int(tpl['amount'])} руб., {tpl['category']}."
            if overspend:
                msg += f"\n⚠ Перерасход по {tpl['category']}"
            send_message(chat_id, msg, build_main_menu_keyboard())
        return

    # Settings
    if data == "settings_quiet_hours":
        set_state(chat_id, "settings_quiet", "0", {})
        send_message(chat_id, "Введите тихие часы (два числа: начало конец), например: 23 7", build_cancel_keyboard())
        return
    if data == "settings_notifications":
        _handle_settings_notifications(chat_id, session)
        return
    if data == "settings_threshold":
        set_state(chat_id, "settings_threshold", "0", {})
        current = get_config_param(session, "LargeExpenseThreshold") or "10000"
        send_message(chat_id, f"Текущий порог: {current} руб. Новый порог:", build_cancel_keyboard())
        return
    if data == "settings_delete_all":
        set_state(chat_id, "delete_all_confirm", "0", {})
        send_message(chat_id, "⚠ Все данные будут удалены!\nНапишите УДАЛИТЬ для подтверждения.", build_cancel_keyboard())
        return

    # Date choice for expense
    if data == "date_today":
        set_state(chat_id, "expense_amount", "0", {"custom_date": calc_today()})
        send_message(chat_id, "Сумма расхода:", build_cancel_keyboard())
        return
    if data == "date_yesterday":
        set_state(chat_id, "expense_amount", "0", {"custom_date": calc_yesterday()})
        send_message(chat_id, "Сумма расхода:", build_cancel_keyboard())
        return
    if data == "date_custom":
        set_state(chat_id, "custom_date_expense", "0", {})
        send_message(chat_id, "Введите дату (YYYY-MM-DD):", build_cancel_keyboard())
        return


# ─── Feature handlers ──────────────────────────────────────────
def _handle_budget_status(chat_id, session):
    st = get_budget_status(session)
    lines = [f"Бюджет на {st['month_year']}", ""]
    if st["limits"]:
        for cat in EXPENSE_CATEGORIES:
            lim = st["limits"].get(cat)
            sp = st["spent"].get(cat, 0)
            if lim is not None:
                pct = int(100 * sp / lim) if lim else 0
                warn = " ⚠" if sp > lim else ""
                lines.append(f"{cat}: {int(sp)}/{int(lim)} ({pct}%){warn}")
        if st["over"]:
            lines.append("")
            for o in st["over"]:
                lines.append(f"⚠ {o['category']}: перерасход {int(o['over'])} руб.")
    else:
        lines.append("План не задан.")
    forecast = get_forecast_end_of_month(session)
    lines.append("")
    lines.append(f"Прогноз: {forecast['forecast_balance']} руб. к концу месяца ({forecast['days_left']} дн.)")
    hint = get_5030_20_hint(session)
    if "Нет данных" not in hint and "Нет доходов" not in hint:
        lines.append("")
        lines.append(hint)
    send_message(chat_id, "\n".join(lines), build_budget_keyboard())


def _handle_budget_suggest(chat_id, session):
    suggested = suggest_plan_from_history(session)
    if not suggested:
        send_message(chat_id, "Нет данных за прошлые месяцы.", build_budget_keyboard())
        return
    lines = ["Предложение на основе средних за 3 месяца:"]
    for cat, avg in sorted(suggested.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat}: {int(avg)} руб.")
    lines.append("\nЗадать эти лимиты? Нажмите «Задать план на месяц».")
    send_message(chat_id, "\n".join(lines), build_budget_keyboard())


def _handle_budget_forecast(chat_id, session):
    f = get_forecast_end_of_month(session)
    lines = [
        "Прогноз на конец месяца:",
        f"  Доходы: {int(f['income'])} руб.",
        f"  Расходы (текущие): {int(f['spent_so_far'])} руб.",
        f"  Средний/день: {f['daily_avg']} руб.",
        f"  Прогноз расходов: {int(f['projected_expense'])} руб.",
        f"  Прогноз баланса: {f['forecast_balance']} руб.",
        f"  Осталось дней: {f['days_left']}",
    ]
    send_message(chat_id, "\n".join(lines), build_budget_keyboard())


def _handle_goals_list(chat_id, session):
    goals = get_active_goals(session)
    if not goals:
        send_message(chat_id, "Целей пока нет.", build_goals_keyboard())
        return
    from services.goals import get_goal_icon, get_goal_pace_hint
    lines = ["Ваши цели:"]
    for g in goals:
        icon = get_goal_icon(getattr(g, "goal_type", "other") or "other")
        pct = int(100 * g.current_amount / g.target_amount) if g.target_amount else 0
        dl = f" до {g.deadline}" if g.deadline else ""
        hint = get_goal_pace_hint(g)
        lines.append(f"{icon} {g.name}: {int(g.current_amount)}/{int(g.target_amount)} ({pct}%){dl}")
        lines.append(f"    {hint}")
    send_message(chat_id, "\n".join(lines), build_goals_keyboard())


def _handle_debts_list(chat_id, session):
    debts = get_active_debts(session)
    if not debts:
        send_message(chat_id, "Долгов нет.", build_debts_keyboard())
        return
    summary = get_debt_summary(session)
    lines = [f"Долги: я должен {int(summary['owe'])} руб., мне должны {int(summary['lent'])} руб.", ""]
    send_message(chat_id, "\n".join(lines), build_debt_select_keyboard(debts))


def _handle_subs_list(chat_id, session):
    subs = get_active_subscriptions(session)
    if not subs:
        send_message(chat_id, "Подписок нет.", build_subscriptions_keyboard())
        return
    lines = ["Подписки:"]
    for s in subs:
        overdue = " (просрочена!)" if getattr(s, "is_overdue", False) else ""
        lines.append(f"• {s.name}: {int(s.amount)} руб. / {s.cycle}, след. {s.next_date}{overdue}")
    send_message(chat_id, "\n".join(lines), build_subscriptions_keyboard())


def _handle_analytics_chart(chat_id, session):
    from services.budget import get_month_range
    from services.charts import generate_pie_chart
    import os
    month_year = calc_today()[:7]
    start, end = get_month_range(month_year)
    from db.repositories import get_expenses_by_category_for_period
    data = get_expenses_by_category_for_period(session, start, end)
    if not data:
        send_message(chat_id, "Нет данных для диаграммы.", build_analytics_keyboard())
        return
    path = generate_pie_chart(data, f"Расходы {month_year}")
    if path:
        send_photo(chat_id, path, f"Расходы за {month_year}")
        try:
            os.unlink(path)
        except Exception:
            pass
    else:
        lines = ["Расходы по категориям:"]
        for cat, amt in sorted(data.items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: {int(amt)} руб.")
        send_message(chat_id, "\n".join(lines), build_analytics_keyboard())


def _handle_analytics_top(chat_id, session):
    from services.reports import get_top_expenses, get_period_range
    start, end = get_period_range("month")
    top = get_top_expenses(session, start, end, 5)
    if not top:
        send_message(chat_id, "Нет расходов.", build_analytics_keyboard())
        return
    lines = ["Топ-5 расходов за месяц:"]
    for i, r in enumerate(top, 1):
        lines.append(f"  {i}. {int(r.amount)} руб. — {r.category or '?'} ({r.date}) {r.comment or ''}")
    send_message(chat_id, "\n".join(lines), build_analytics_keyboard())


def _handle_history(chat_id, session, period):
    from datetime import datetime, timedelta
    today = calc_today()
    if period == "today":
        entries = get_finance_for_period(session, today, today)
    elif period == "week":
        start = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
        entries = get_finance_for_period(session, start, today)
    else:
        start = today[:7] + "-01"
        entries = get_finance_for_period(session, start, today)
    if not entries:
        send_message(chat_id, "Нет записей.", build_history_keyboard())
        return
    lines = [f"История ({period}): {len(entries)} записей"]
    for r in entries[-15:]:
        t = "+" if r.type in ("IncomeSalary", "IncomeSecond") else "-"
        lines.append(f"  {r.date} {t}{int(r.amount)} {r.category or ''} {r.comment or ''}")
    send_message(chat_id, "\n".join(lines), build_recent_entries_keyboard(entries[-5:]))


def _handle_settings_notifications(chat_id, session):
    quiet_start = get_config_param(session, "QuietHoursStart") or "не задано"
    quiet_end = get_config_param(session, "QuietHoursEnd") or "не задано"
    threshold = get_config_param(session, "LargeExpenseThreshold") or "10000"
    msg = (
        f"Тихие часы: {quiet_start} — {quiet_end}\n"
        f"Порог крупного расхода: {threshold} руб."
    )
    send_message(chat_id, msg, build_settings_keyboard())


def _handle_export(chat_id, session):
    import json
    import tempfile
    import os
    export_dict = _export_data_json(session)
    payload = json.dumps(export_dict, ensure_ascii=False, indent=2)
    path = None
    try:
        fd, path = tempfile.mkstemp(suffix=".json", prefix="monelanal_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        send_document(chat_id, path, "Экспорт данных MonelANAL")
    except Exception as e:
        send_message(chat_id, f"Ошибка экспорта: {e}", build_main_menu_keyboard())
    finally:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except Exception:
                pass


def handle_help(chat_id: int):
    msg = (
        "Статус — ЗП, бюджет\n"
        "Расход — записать расход (или /расход 500 еда)\n"
        "Доход — записать доход\n"
        "Бюджет — план, лимиты, прогноз, 50/30/20\n"
        "Цели — накопления (типы, авто-пополнение)\n"
        "Долги — учёт долгов и кредитов\n"
        "Подписки — регулярные платежи\n"
        "Аналитика — отчёты, графики, сравнения\n"
        "История — просмотр операций\n"
        "Шаблоны — быстрые расходы\n"
        "Настройки — тихие часы, пороги, экспорт\n"
        "/редактировать — изменить/удалить расход"
    )
    send_message(chat_id, msg, build_main_menu_keyboard())


def handle_status(chat_id: int, session):
    try:
        today = calc_today()
        acc = get_accrued_summary_for_payday(session)
        next_pay = get_next_pay_date(today, session)
        balance = get_budget_balance(session)
        start_month = today[:7] + "-01"
        second_month = get_accrued_second_for_period(start_month, today, session)
        debt_sum = get_debt_summary(session)
        log_info(session, f"handleStatus: balance={balance}")
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
    send_message(chat_id, f"За вчера ({yesterday}): заказов {len(orders)}, сумма {int(total)} руб.")


def _handle_edit_last_menu(chat_id: int, session):
    last = get_last_finance_entry(session, "Expense", 1)
    if not last:
        send_message(chat_id, "Нет расходов для редактирования.", build_main_menu_keyboard())
        return
    r = last[0]
    send_message(
        chat_id,
        f"Последний расход: {r.amount} руб., {r.category or '—'} ({r.date}). Что сделать?",
        build_edit_last_keyboard(),
    )


def handle_monthly_report(chat_id: int, session) -> str:
    today = calc_today()
    month_year = today[:7]
    start, end = get_month_range(month_year)
    rows = get_finance_for_period(session, start, end)
    income = expense = 0
    by_cat = {}
    for r in rows:
        amt = r.amount or 0
        if r.type in ("IncomeSalary", "IncomeSecond"):
            income += amt
        elif r.type == "Expense":
            expense += amt
            by_cat[r.category or "Без категории"] = by_cat.get(r.category or "Без категории", 0) + amt
    limits = get_budget_limits_map(session, month_year)
    lines = [
        f"Отчёт за {month_year}",
        f"Доходы: {int(income)} руб.",
        f"Расходы: {int(expense)} руб.",
        f"Баланс: {int(income - expense)} руб.",
        "", "По категориям:",
    ]
    for cat in sorted(by_cat.keys(), key=lambda c: -by_cat[c]):
        lim = limits.get(cat, "")
        suf = f" (лимит {int(lim)})" if lim else ""
        lines.append(f"  {cat}: {int(by_cat[cat])}{suf}")
    # Rosstat comparison
    ROSSTAT_AVG = {"Еда": 18000, "Транспорт": 5000, "Жильё": 12000, "Здоровье": 3000, "Развлечения": 4000, "Прочее": 6000}
    rosstat_lines = []
    for cat, norm in ROSSTAT_AVG.items():
        actual = by_cat.get(cat, 0)
        if actual > 0:
            diff_pct = int((actual - norm) / norm * 100) if norm else 0
            sign = "+" if diff_pct >= 0 else ""
            rosstat_lines.append(f"  {cat}: {sign}{diff_pct}% от нормы")
    if rosstat_lines:
        lines.append("")
        lines.append("Сравнение с нормой РФ:")
        lines.extend(rosstat_lines)
    return "\n".join(lines)


def _export_data_json(session) -> dict:
    from db.models import WorkLog, Order, Finance, Config, BudgetPlan, Goal, Subscription, Calculation, Debt, DebtPayment
    config_rows = session.query(Config).all()
    config = {r.parameter: r.value for r in config_rows}
    worklog = [{"id": r.id, "date": r.date, "job_type": r.job_type, "hours": r.hours_worked, "status": r.status} for r in session.query(WorkLog).all()]
    orders = [{"id": r.order_id, "date": r.date, "description": r.description, "amount": r.amount} for r in session.query(Order).all()]
    finance = [{"id": r.id, "date": r.date, "type": r.type, "amount": r.amount, "category": r.category, "comment": r.comment} for r in session.query(Finance).all()]
    budget = [{"month_year": r.month_year, "category": r.category, "limit": r.limit_amount} for r in session.query(BudgetPlan).all()]
    goals = [{"id": r.id, "name": r.name, "target": r.target_amount, "current": r.current_amount, "deadline": r.deadline} for r in session.query(Goal).all()]
    subs = [{"id": r.id, "name": r.name, "amount": r.amount, "cycle": r.cycle, "next_date": r.next_date} for r in session.query(Subscription).all()]
    debts = [{"id": r.id, "direction": r.direction, "counterparty": r.counterparty, "original": r.original_amount, "remaining": r.remaining_amount} for r in session.query(Debt).all()]
    return {
        "export_date": calc_today(),
        "config": config,
        "worklog": worklog,
        "orders": orders,
        "finance": finance,
        "budget_plan": budget,
        "goals": goals,
        "subscriptions": subs,
        "debts": debts,
    }
