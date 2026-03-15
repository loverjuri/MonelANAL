"""Message and callback handlers. FSM logic for all features."""
from db.repositories import (
    get_session,
    add_work_log,
    get_work_log,
    get_work_log_for_period,
    update_work_log,
    add_order,
    add_order_with_items,
    add_finance_entry,
    record_payday_received,
    get_orders_for_period,
    get_order,
    update_order,
    delete_order,
    get_budget_limits_map,
    set_budget_plan_limit,
    get_active_goals,
    add_goal,
    update_goal_current,
    get_goal,
    get_active_subscriptions,
    get_inactive_subscriptions,
    get_subscription,
    add_subscription,
    get_subscriptions_due_soon,
    update_subscription,
    delete_subscription,
    get_last_finance_entry,
    get_finance_by_id,
    update_finance_entry,
    delete_finance_entry,
    soft_delete_finance_entry,
    mass_finance_operations,
    log_audit,
    has_finance_duplicate,
    get_finance_for_period,
    log_info,
    log_error,
    # Phase 1: Debts
    add_debt,
    get_active_debts,
    get_debt,
    add_debt_payment,
    get_debt_payments,
    get_debt_payment,
    get_debt_summary,
    update_debt,
    update_debt_remaining_with_comment,
    update_debt_payment,
    delete_debt_payment,
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
    get_tags,
    add_tag,
    update_tag,
    delete_tag,
    get_templates,
    get_template,
    add_template,
    update_template,
    delete_template,
    use_template,
    # Phase 4: Goals ext
    archive_goal,
    get_archived_goals,
    update_goal,
    transfer_between_goals,
    # Phase 9: Achievements
    get_achievements,
    delete_achievement,
    get_calculations,
    get_calculation,
    update_calculation,
    # Config
    get_config_param,
    set_config_param,
)
from services.state import get_state, set_state, clear_state
from db.repositories import get_state as get_state_db
from services.calculations import (
    get_today_msk as calc_today,
    get_yesterday_msk as calc_yesterday,
    get_accrued_summary_for_payday,
    get_next_pay_date,
    get_budget_balance,
    get_accrued_second_for_period,
    calc_hour_rate_snapshot_for_date,
)
from bot.telegram_api import send_message, answer_callback_query, send_document, send_photo, download_file
from services.budget import (
    get_budget_status, get_month_range, check_category_overspend,
    suggest_plan_from_history, get_forecast_end_of_month, get_5030_20_hint,
)
from bot.keyboards import (
    _inline_keyboard,
    _btn,
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
    build_worklog_period_keyboard,
    build_worklog_list_keyboard,
    build_orders_period_keyboard,
    build_orders_list_keyboard,
    build_goals_keyboard,
    build_goal_select_keyboard,
    build_goal_detail_keyboard,
    build_goal_edit_field_keyboard,
    build_goal_transfer_target_keyboard,
    build_subscriptions_keyboard,
    build_subs_select_keyboard,
    build_subs_detail_keyboard,
    build_subs_edit_field_keyboard,
    build_subs_cycle_keyboard,
    build_subs_group_keyboard,
    build_edit_last_keyboard,
    build_debts_keyboard,
    build_debt_direction_keyboard,
    build_debt_detail_keyboard,
    build_debt_edit_field_keyboard,
    build_debt_cycle_edit_keyboard,
    build_debt_kind_edit_keyboard,
    build_debt_history_keyboard,
    build_debt_select_keyboard,
    build_debt_kind_keyboard,
    build_debt_payment_mode_keyboard,
    build_debt_payment_type_keyboard,
    build_debt_cycle_keyboard,
    build_debt_confirm_payment_keyboard,
    build_analytics_keyboard,
    build_period_keyboard,
    build_history_keyboard,
    build_templates_keyboard,
    build_tpl_edit_keyboard,
    build_settings_keyboard,
    build_config_params_keyboard,
    build_edit_menu_keyboard,
    build_tags_keyboard,
    build_achievements_keyboard,
    build_calculations_keyboard,
    build_mass_period_keyboard,
    build_mass_category_keyboard,
    build_mass_action_keyboard,
    CONFIG_PARAMS,
    build_goal_type_keyboard,
    build_goal_type_keyboard_for_edit,
    build_confirm_keyboard,
    build_date_choice_keyboard,
    build_recent_entries_keyboard,
    build_finance_edit_field_keyboard,
    build_finance_type_keyboard,
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
def handle_message(chat_id: int, text: str, message_id: int | None = None, message: dict | None = None):
    session = get_session()
    try:
        state = get_state(chat_id)
        trimmed = (text or "").strip()

        # Document upload for Excel import
        if message and message.get("document") and state and state.get("scenario") == "import_excel_wait_file":
            _handle_import_excel_document(chat_id, session, state, message)
            return

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
        if scenario == "finance_edit":
            _fsm_finance_edit(chat_id, session, state, trimmed)
            return
        if scenario == "finance_soft_delete_confirm":
            _fsm_finance_soft_delete_confirm(chat_id, session, state, trimmed)
            return
        if scenario == "budget_set_amount":
            _fsm_budget_set_amount(chat_id, session, state, trimmed)
            return
        if scenario == "budget_bulk":
            _fsm_budget_bulk(chat_id, session, state, trimmed)
            return
        if scenario == "worklog_edit":
            _fsm_worklog_edit(chat_id, session, state, trimmed)
            return
        if scenario == "worklog_add_past":
            _fsm_worklog_add_past(chat_id, session, state, trimmed)
            return
        if scenario == "orders_add_past":
            _fsm_orders_add_past(chat_id, session, state, trimmed)
            return
        if scenario == "order_edit":
            _fsm_order_edit(chat_id, session, state, trimmed)
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
        if scenario == "debt_edit":
            _fsm_debt_edit(chat_id, session, state, trimmed)
            return
        if scenario == "debt_remaining_comment":
            _fsm_debt_remaining_comment(chat_id, session, state, trimmed)
            return
        if scenario == "debt_pay_add":
            _fsm_debt_pay_add(chat_id, session, state, trimmed)
            return
        if scenario == "debt_payment_edit":
            _fsm_debt_payment_edit(chat_id, session, state, trimmed)
            return
        if scenario == "goal_edit":
            _fsm_goal_edit(chat_id, session, state, trimmed)
            return
        if scenario == "goal_transfer_amount":
            _fsm_goal_transfer_amount(chat_id, session, state, trimmed)
            return
        if scenario == "subs_edit":
            _fsm_subs_edit(chat_id, session, state, trimmed)
            return
        if scenario == "tpl_edit":
            _fsm_tpl_edit(chat_id, session, state, trimmed)
            return
        if scenario == "subs_delete_confirm":
            if trimmed.strip().upper() == "ДА":
                sub_id = state["payload"].get("sub_id", "")
                if delete_subscription(session, sub_id):
                    log_audit(session, chat_id, "subscription", sub_id, "delete", None, None, None)
                    clear_state(chat_id)
                    send_message(chat_id, "Подписка удалена.", build_main_menu_keyboard())
                else:
                    clear_state(chat_id)
                    send_message(chat_id, "Ошибка удаления.", build_main_menu_keyboard())
            else:
                send_message(chat_id, "Напишите ДА для подтверждения.", build_cancel_keyboard())
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
        if scenario == "config_edit":
            _fsm_config_edit(chat_id, session, state, trimmed)
            return
        if scenario == "tag_add":
            if trimmed.strip():
                add_tag(session, trimmed.strip())
                log_audit(session, chat_id, "tag", trimmed.strip(), "create", None, None, None)
                tags = get_tags(session)
                clear_state(chat_id)
                send_message(chat_id, f"Тег «{trimmed.strip()}» добавлен.", build_tags_keyboard(tags))
            else:
                send_message(chat_id, "Введите название.", build_cancel_keyboard())
            return
        if scenario == "tag_rename":
            tag_id = state["payload"].get("tag_id", "")
            if trimmed.strip() and tag_id:
                if update_tag(session, tag_id, name=trimmed.strip()):
                    log_audit(session, chat_id, "tag", tag_id, "update", "name", None, trimmed.strip())
                tags = get_tags(session)
                clear_state(chat_id)
                send_message(chat_id, f"Тег переименован в «{trimmed.strip()}»", build_tags_keyboard(tags))
            else:
                send_message(chat_id, "Введите название.", build_cancel_keyboard())
            return
        if scenario == "finance_mass_confirm":
            if trimmed.strip().upper() == "ДА":
                p = state["payload"]
                cat = p.get("category") if p.get("category") != "all" else None
                cnt = mass_finance_operations(session, p["start"], p["end"], category=cat, action=p.get("action", "soft_delete"))
                log_audit(session, chat_id, "finance", "mass", p.get("action", ""), str(cnt), None, None)
                clear_state(chat_id)
                act = "удалено" if p.get("action") == "soft_delete" else "исключено из бюджета"
                send_message(chat_id, f"Массовая операция: {act} {cnt} записей.", build_main_menu_keyboard())
            else:
                send_message(chat_id, "Напишите ДА для подтверждения.", build_cancel_keyboard())
            return
        if scenario == "calc_edit":
            parts = trimmed.strip().split()
            if len(parts) >= 2:
                try:
                    accrued = float(parts[0].replace(",", "."))
                    received = float(parts[1].replace(",", "."))
                    calc_id = state["payload"].get("calc_id")
                    if update_calculation(session, calc_id, accrued_salary=accrued, received_salary=received, difference=accrued - received):
                        log_audit(session, chat_id, "calculation", str(calc_id), "update", None, None, None)
                    clear_state(chat_id)
                    send_message(chat_id, f"Обновлено: начислено {accrued}, получено {received}", build_settings_keyboard())
                except ValueError:
                    send_message(chat_id, "Введите два числа через пробел.", build_cancel_keyboard())
            else:
                send_message(chat_id, "Введите: начислено получено", build_cancel_keyboard())
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
        if scenario == "import_excel_confirm":
            _fsm_import_excel_confirm(chat_id, session, state, trimmed)
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


def _show_finance_edit_field_select(chat_id, session, fid, entry):
    set_state(chat_id, "finance_edit", "field_select", {"finance_id": fid, "back_data": "cmd_history"})
    txt = f"Редактирование: {entry.date} {entry.category} {entry.amount} руб."
    send_message(chat_id, txt, build_finance_edit_field_keyboard(fid))


def _fsm_finance_edit(chat_id, session, state, trimmed):
    step = state.get("step", "")
    fid = state["payload"].get("finance_id", "")
    field = state["payload"].get("field", "")
    if step != "value" or not fid or not field:
        return
    entry = get_finance_by_id(session, fid)
    if not entry:
        clear_state(chat_id)
        send_message(chat_id, "Запись не найдена.", build_main_menu_keyboard())
        return
    if field == "amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt > 0:
            old_v = str(entry.amount)
            if update_finance_entry(session, fid, amount=amt):
                log_audit(session, chat_id, "finance", fid, "update", "amount", old_v, str(amt))
                clear_state(chat_id)
                send_message(chat_id, f"Сумма обновлена: {amt} руб.", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите положительное число:", build_cancel_keyboard())
        return
    if field == "date":
        date_val = trimmed.strip()[:10]
        if len(date_val) >= 8 and date_val.replace("-", "").replace(".", "").isdigit():
            old_v = str(entry.date)
            if update_finance_entry(session, fid, date=date_val):
                log_audit(session, chat_id, "finance", fid, "update", "date", old_v, date_val)
                clear_state(chat_id)
                send_message(chat_id, f"Дата обновлена: {date_val}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Формат: YYYY-MM-DD", build_cancel_keyboard())
        return
    if field == "category":
        cat = trimmed.strip() if trimmed.strip() in EXPENSE_CATEGORIES else None
        if cat:
            old_v = str(entry.category or "")
            if update_finance_entry(session, fid, category=cat):
                log_audit(session, chat_id, "finance", fid, "update", "category", old_v, cat)
                clear_state(chat_id)
                send_message(chat_id, f"Категория: {cat}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Выберите категорию из списка.", build_expense_categories_keyboard())
        return
    if field == "comment":
        old_v = str(entry.comment or "")
        new_v = trimmed.strip() if trimmed else ""
        if update_finance_entry(session, fid, comment=new_v):
            log_audit(session, chat_id, "finance", fid, "update", "comment", old_v, new_v)
            clear_state(chat_id)
            send_message(chat_id, "Комментарий обновлён.", build_main_menu_keyboard())
        return


def _fsm_finance_soft_delete_confirm(chat_id, session, state, trimmed):
    if trimmed.strip().upper() != "ДА":
        send_message(chat_id, "Напишите ДА для подтверждения удаления или отмените.", build_cancel_keyboard())
        return
    fid = state["payload"].get("finance_id", "")
    if soft_delete_finance_entry(session, fid):
        log_audit(session, chat_id, "finance", fid, "soft_delete", None, None, None)
        clear_state(chat_id)
        send_message(chat_id, "Запись удалена (скрыта из отчётов).", build_main_menu_keyboard())
    else:
        clear_state(chat_id)
        send_message(chat_id, "Ошибка удаления.", build_main_menu_keyboard())


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


def _fsm_budget_bulk(chat_id, session, state, trimmed):
    month_year = state["payload"].get("month_year", calc_today()[:7])
    count = 0
    for line in trimmed.strip().split("\n"):
        line = line.strip()
        if ":" in line:
            cat, amt_str = line.split(":", 1)
            cat = cat.strip()
            try:
                amt = float(amt_str.replace(" ", "").replace(",", "."))
            except ValueError:
                continue
            if cat in EXPENSE_CATEGORIES and amt >= 0:
                set_budget_plan_limit(session, month_year, cat, amt)
                log_audit(session, chat_id, "budget", month_year, "update", cat, None, str(amt))
                count += 1
    clear_state(chat_id)
    send_message(chat_id, f"Задано лимитов: {count}", build_main_menu_keyboard())


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


def _fsm_subs_edit(chat_id, session, state, trimmed):
    step = state.get("step", "")
    sub_id = state["payload"].get("sub_id", "")
    field = state["payload"].get("field", "")
    s = get_subscription(session, sub_id)
    if not s:
        clear_state(chat_id)
        send_message(chat_id, "Подписка не найдена.", build_main_menu_keyboard())
        return
    if step != "value" or not field:
        return
    if field == "name":
        new_val = trimmed.strip()
        if new_val:
            old_v = str(s.name)
            if update_subscription(session, sub_id, name=new_val):
                log_audit(session, chat_id, "subscription", sub_id, "update", "name", old_v, new_val)
            clear_state(chat_id)
            send_message(chat_id, f"Название: {new_val}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите название.", build_cancel_keyboard())
        return
    if field == "amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt > 0:
            old_v = str(s.amount)
            if update_subscription(session, sub_id, amount=amt):
                log_audit(session, chat_id, "subscription", sub_id, "update", "amount", old_v, str(amt))
            clear_state(chat_id)
            send_message(chat_id, f"Сумма: {amt} руб.", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите положительное число.", build_cancel_keyboard())
        return
    if field == "next_date":
        date_val = trimmed.strip()[:10] if trimmed.strip() else ""
        if len(date_val) >= 8 and date_val.replace("-", "").replace(".", "").isdigit():
            old_v = str(s.next_date or "")
            if update_subscription(session, sub_id, next_date=date_val):
                log_audit(session, chat_id, "subscription", sub_id, "update", "next_date", old_v, date_val)
            clear_state(chat_id)
            send_message(chat_id, f"Дата: {date_val}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Формат: YYYY-MM-DD", build_cancel_keyboard())
        return
    if field == "remind_days_before":
        try:
            days = int(float(trimmed.replace(" ", "").replace(",", ".")))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if days >= 0:
            old_v = str(s.remind_days_before or 0)
            if update_subscription(session, sub_id, remind_days_before=days):
                log_audit(session, chat_id, "subscription", sub_id, "update", "remind_days_before", old_v, str(days))
            clear_state(chat_id)
            send_message(chat_id, f"Напоминание за {days} дн.", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите неотрицательное число.", build_cancel_keyboard())
        return


def _fsm_worklog_edit(chat_id, session, state, trimmed):
    wl_id = state["payload"].get("wl_id", "")
    w = get_work_log(session, wl_id)
    if not w:
        clear_state(chat_id)
        send_message(chat_id, "Запись не найдена.", build_main_menu_keyboard())
        return
    parts = trimmed.strip().split()
    hrs_str = parts[0] if parts else "0"
    status = "Work"
    if len(parts) >= 2:
        st_lower = parts[1].lower()
        if "sick" in st_lower or "боль" in st_lower:
            status = STATUS_SICK
        elif "weekend" in st_lower or "выход" in st_lower:
            status = STATUS_WEEKEND_WORK
        else:
            status = STATUS_WORK
    try:
        hours = float(hrs_str.replace(",", "."))
    except ValueError:
        send_message(chat_id, "Введите: часы [статус]. Пример: 6 Work", build_cancel_keyboard())
        return
    if hours < 0 or hours > 24:
        send_message(chat_id, "Часы: 0–24.", build_cancel_keyboard())
        return
    old_h = str(w.hours_worked)
    old_s = str(w.status)
    if update_work_log(session, wl_id, hours_worked=hours, status=status):
        log_audit(session, chat_id, "worklog", wl_id, "update", "hours_worked", old_h, str(hours))
        log_audit(session, chat_id, "worklog", wl_id, "update", "status", old_s, status)
    clear_state(chat_id)
    send_message(chat_id, f"Обновлено: {hours}ч {status}", build_main_menu_keyboard())


def _fsm_worklog_add_past(chat_id, session, state, trimmed):
    """Parse dates (11-13, 11 12 13, or full YYYY-MM-DD) and add 8h Work for each."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Moscow")
    today = datetime.now(tz)
    year_month = f"{today.year}-{today.month:02d}"
    dates = []
    parts = trimmed.strip().replace(",", " ").split()
    for p in parts:
        p = p.strip()
        if "-" in p and len(p) <= 5:
            try:
                start_d, end_d = p.split("-", 1)
                s, e = int(start_d), int(end_d)
                for d in range(s, e + 1):
                    dates.append(f"{year_month}-{d:02d}")
            except ValueError:
                pass
            continue
        if p.isdigit():
            d = int(p)
            if 1 <= d <= 31:
                dates.append(f"{year_month}-{d:02d}")
            continue
        if len(p) == 10 and p[4] == "-" and p[7] == "-":
            try:
                datetime.strptime(p[:10], "%Y-%m-%d")
                dates.append(p[:10])
            except ValueError:
                pass
    dates = sorted(set(dates))
    if not dates:
        send_message(chat_id, "Не удалось распознать даты. Примеры: 11-13 или 11 12 13", build_cancel_keyboard())
        return
    norm = 8
    try:
        from services.calculations import _get_work_hours_norm
        norm = _get_work_hours_norm(session)
    except Exception:
        pass
    added = []
    for date_str in dates:
        hour_rate = calc_hour_rate_snapshot_for_date(date_str, session)
        add_work_log(session, date_str, JOB_MAIN, norm, STATUS_WORK, hour_rate)
        added.append(date_str)
    clear_state(chat_id)
    lines = [f"Записано {len(added)} дней по {norm} ч:"]
    for d in added:
        lines.append(f"  {d}")
    send_message(chat_id, "\n".join(lines), build_main_work_keyboard())


def _fsm_orders_add_past(chat_id, session, state, trimmed):
    """Parse lines 'date desc amount' and add orders. Date: 11 or 2026-03-11."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Moscow")
    today = datetime.now(tz)
    year_month = f"{today.year}-{today.month:02d}"
    added = []
    for line in trimmed.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        date_part = parts[0]
        try:
            amount = float(parts[-1].replace(",", ".").replace(" ", ""))
        except ValueError:
            continue
        desc = " ".join(parts[1:-1]).strip()
        if not desc:
            desc = "Заказ"
        if len(date_part) == 10 and date_part[4] == "-" and date_part[7] == "-":
            try:
                datetime.strptime(date_part[:10], "%Y-%m-%d")
                date_str = date_part[:10]
            except ValueError:
                continue
        elif date_part.isdigit():
            d = int(date_part)
            if 1 <= d <= 31:
                date_str = f"{year_month}-{d:02d}"
            else:
                continue
        else:
            continue
        add_order(session, date_str, desc, amount)
        added.append((date_str, desc, amount))
    if not added:
        send_message(chat_id, "Не удалось распознать заказы. Формат: дата описание сумма (каждая строка — один заказ)", build_cancel_keyboard())
        return
    clear_state(chat_id)
    lines = [f"Добавлено {len(added)} заказ(ов):"]
    for d, desc, amt in added:
        lines.append(f"  {d}: {desc} — {int(amt)} руб.")
    send_message(chat_id, "\n".join(lines), build_second_job_keyboard())


def _fsm_order_edit(chat_id, session, state, trimmed):
    order_id = state["payload"].get("order_id", "")
    o = get_order(session, order_id)
    if not o:
        clear_state(chat_id)
        send_message(chat_id, "Заказ не найден.", build_main_menu_keyboard())
        return
    parts = trimmed.strip().split()
    if len(parts) < 3:
        send_message(chat_id, "Введите: дата описание сумма. Пример: 2024-03-15 Доставка 1500", build_cancel_keyboard())
        return
    date_val = parts[0]
    if len(date_val) >= 10 and date_val[4] == "-" and date_val[7] == "-":
        try:
            amt = float(parts[-1].replace(",", "."))
        except ValueError:
            send_message(chat_id, "Сумма должна быть числом.", build_cancel_keyboard())
            return
        desc = " ".join(parts[1:-1])
        old_d = str(o.date)
        old_desc = str(o.description or "")
        old_a = str(o.amount)
        if update_order(session, order_id, date=date_val, description=desc, amount=amt):
            log_audit(session, chat_id, "order", order_id, "update", "date", old_d, date_val)
            log_audit(session, chat_id, "order", order_id, "update", "amount", old_a, str(amt))
        clear_state(chat_id)
        send_message(chat_id, f"Заказ обновлён: {date_val} {desc} {int(amt)} руб.", build_second_job_keyboard())
    else:
        send_message(chat_id, "Формат даты: YYYY-MM-DD", build_cancel_keyboard())


def _fsm_debts_add(chat_id, session, state, trimmed):
    step = state.get("step", "")
    p = state.get("payload", {})
    if step == "counterparty":
        set_state(chat_id, "debts_add", "amount", {**p, "counterparty": trimmed})
        send_message(chat_id, "Сумма долга (руб):", build_cancel_keyboard())
        return
    if step == "amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt > 0:
            set_state(chat_id, "debts_add", "interest", {**p, "amount": amt})
            send_message(chat_id, "Процентная ставка (0 если без процентов):", build_cancel_keyboard())
        return
    if step == "interest":
        try:
            rate = float(trimmed.replace(",", "."))
        except ValueError:
            rate = 0
        set_state(chat_id, "debts_add", "debt_kind", {**p, "interest": rate})
        send_message(chat_id, "Тип долга:", build_debt_kind_keyboard())
        return
    if step == "months":
        try:
            months = int(trimmed.replace(" ", ""))
        except ValueError:
            send_message(chat_id, "Введите число месяцев:", build_cancel_keyboard())
            return
        if months > 0:
            set_state(chat_id, "debts_add", "payment_type", {**p, "months": months})
            send_message(chat_id, "Тип графика платежа:", build_debt_payment_type_keyboard())
        return
    if step == "monthly_payment":
        try:
            pmt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите сумму платежа (руб):", build_cancel_keyboard())
            return
        if pmt > 0:
            set_state(chat_id, "debts_add", "cycle", {**p, "monthly_payment": pmt})
            send_message(chat_id, "Интервал платежей:", build_debt_cycle_keyboard())
        return
    if step == "next_payment_date":
        dt = trimmed[:10] if len(trimmed) >= 10 else ""
        if dt and dt[4] == "-" and dt[7] == "-":
            set_state(chat_id, "debts_add", "due_date", {**p, "next_payment_date": dt})
            send_message(chat_id, "Дата окончания (YYYY-MM-DD или '-'):", build_cancel_keyboard())
        else:
            send_message(chat_id, "Неверный формат. Используйте YYYY-MM-DD:", build_cancel_keyboard())
        return
    if step == "due_date":
        due = "" if trimmed in ("-", "нет", "") else trimmed[:10]
        _save_debt(chat_id, session, {**p, "due_date": due})


def _save_debt(chat_id, session, p: dict):
    add_debt(
        session,
        p.get("direction", "owe"),
        p["counterparty"],
        p["amount"],
        p.get("interest", 0),
        p.get("payment_type", "fixed"),
        p.get("monthly_payment", 0),
        p.get("payment_cycle", "monthly"),
        p.get("next_payment_date", ""),
        p.get("debt_kind", "credit"),
        p.get("due_date", ""),
    )
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


def _fsm_debt_edit(chat_id, session, state, trimmed):
    step = state.get("step", "")
    debt_id = state["payload"].get("debt_id", "")
    field = state["payload"].get("field", "")
    debt = get_debt(session, debt_id)
    if not debt:
        clear_state(chat_id)
        send_message(chat_id, "Долг не найден.", build_main_menu_keyboard())
        return
    if step != "value" or not field:
        return
    if field == "counterparty":
        new_val = trimmed.strip()
        if new_val:
            old_v = str(debt.counterparty)
            if update_debt(session, debt_id, counterparty=new_val):
                log_audit(session, chat_id, "debt", debt_id, "update", "counterparty", old_v, new_val)
            clear_state(chat_id)
            send_message(chat_id, f"Контрагент: {new_val}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите название контрагента.", build_cancel_keyboard())
        return
    if field == "original_amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt > 0:
            old_v = str(debt.original_amount)
            if update_debt(session, debt_id, original_amount=amt):
                log_audit(session, chat_id, "debt", debt_id, "update", "original_amount", old_v, str(amt))
            clear_state(chat_id)
            send_message(chat_id, f"Сумма: {amt} руб.", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите положительное число.", build_cancel_keyboard())
        return
    if field == "interest_rate":
        try:
            rate = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if rate >= 0:
            old_v = str(debt.interest_rate or 0)
            if update_debt(session, debt_id, interest_rate=rate):
                log_audit(session, chat_id, "debt", debt_id, "update", "interest_rate", old_v, str(rate))
            clear_state(chat_id)
            send_message(chat_id, f"Ставка: {rate}%", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите неотрицательное число.", build_cancel_keyboard())
        return
    if field == "monthly_payment":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt >= 0:
            old_v = str(debt.monthly_payment or 0)
            if update_debt(session, debt_id, monthly_payment=amt):
                log_audit(session, chat_id, "debt", debt_id, "update", "monthly_payment", old_v, str(amt))
            clear_state(chat_id)
            send_message(chat_id, f"Платёж: {amt} руб.", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите неотрицательное число.", build_cancel_keyboard())
        return
    if field == "next_payment_date":
        date_val = trimmed.strip()[:10] if trimmed.strip() else ""
        if not date_val or (len(date_val) >= 8 and date_val.replace("-", "").replace(".", "").isdigit()):
            old_v = str(debt.next_payment_date or "")
            if update_debt(session, debt_id, next_payment_date=date_val or None):
                log_audit(session, chat_id, "debt", debt_id, "update", "next_payment_date", old_v, date_val or "None")
            clear_state(chat_id)
            send_message(chat_id, f"Дата: {date_val or 'сброшена'}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Формат: YYYY-MM-DD или пусто", build_cancel_keyboard())
        return
    if field == "due_date":
        date_val = trimmed.strip()[:10] if trimmed.strip() else ""
        if not date_val or (len(date_val) >= 8 and date_val.replace("-", "").replace(".", "").isdigit()):
            old_v = str(debt.due_date or "")
            if update_debt(session, debt_id, due_date=date_val or ""):
                log_audit(session, chat_id, "debt", debt_id, "update", "due_date", old_v, date_val or "")
            clear_state(chat_id)
            send_message(chat_id, f"Срок: {date_val or 'сброшен'}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Формат: YYYY-MM-DD или пусто", build_cancel_keyboard())
        return


def _fsm_debt_remaining_comment(chat_id, session, state, trimmed):
    debt_id = state["payload"].get("debt_id", "")
    raw = trimmed.strip()
    if not raw:
        send_message(chat_id, "Введите: сумма и комментарий. Пример: 50000 коррекция по договору", build_cancel_keyboard())
        return
    parts = raw.split(None, 1)
    amt_str = parts[0]
    comm = parts[1] if len(parts) > 1 else "вручную"
    try:
        new_remaining = float(amt_str.replace(",", "."))
    except ValueError:
        send_message(chat_id, "Формат: <сумма> [комментарий]. Пример: 50000 коррекция", build_cancel_keyboard())
        return
    if new_remaining < 0:
        send_message(chat_id, "Остаток не может быть отрицательным.", build_cancel_keyboard())
        return
    debt = get_debt(session, debt_id)
    if not debt:
        clear_state(chat_id)
        send_message(chat_id, "Долг не найден.", build_main_menu_keyboard())
        return
    old_v = str(debt.remaining_amount)
    if update_debt_remaining_with_comment(session, debt_id, new_remaining, comm):
        log_audit(session, chat_id, "debt", debt_id, "update", "remaining_amount", old_v, str(new_remaining))
        clear_state(chat_id)
        send_message(chat_id, f"Остаток: {new_remaining} руб. ({comm})", build_main_menu_keyboard())
    else:
        clear_state(chat_id)
        send_message(chat_id, "Ошибка обновления.", build_main_menu_keyboard())


def _fsm_debt_pay_add(chat_id, session, state, trimmed):
    step = state.get("step", "")
    debt_id = state["payload"].get("debt_id", "")
    if step == "amount":
        parts = trimmed.strip().split()
        amt_str = parts[0] if parts else ""
        date_str = parts[1][:10] if len(parts) > 1 else calc_today()
        try:
            amt = float(amt_str.replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите: сумма [дата]. Пример: 5000 2024-03-01", build_cancel_keyboard())
            return
        if amt > 0:
            if len(parts) > 1 and len(parts[1]) >= 8:
                date_str = parts[1][:10]
            else:
                date_str = calc_today()
            pid = add_debt_payment(session, debt_id, amt, date=date_str)
            if pid:
                log_audit(session, chat_id, "debt", debt_id, "create", "payment", None, f"{amt} {date_str}")
                debt = get_debt(session, debt_id)
                payments = get_debt_payments(session, debt_id)
                send_message(chat_id, f"Платёж {int(amt)} руб. ({date_str}) добавлен. Остаток: {int(debt.remaining_amount) if debt else 0}", build_debt_history_keyboard(debt_id, payments))
            else:
                send_message(chat_id, "Ошибка добавления.", build_cancel_keyboard())
            clear_state(chat_id)
        else:
            send_message(chat_id, "Введите положительную сумму.", build_cancel_keyboard())
        return


def _fsm_debt_payment_edit(chat_id, session, state, trimmed):
    step = state.get("step", "")
    pid = state["payload"].get("payment_id", "")
    if step == "amount":
        parts = trimmed.strip().split()
        amt_str = parts[0] if parts else ""
        date_str = parts[1][:10] if len(parts) > 1 else None
        try:
            amt = float(amt_str.replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите: сумма [дата]. Пример: 5000 2024-03-01", build_cancel_keyboard())
            return
        if amt > 0:
            p = get_debt_payment(session, pid)
            if not p:
                clear_state(chat_id)
                send_message(chat_id, "Платёж не найден.", build_main_menu_keyboard())
                return
            kw = {"amount": amt}
            if len(parts) > 1 and len(parts[1]) >= 8:
                kw["date"] = parts[1][:10]
            if update_debt_payment(session, pid, **kw):
                log_audit(session, chat_id, "debt", p.debt_id, "update", "payment", str(p.amount), str(amt))
            debt_id = p.debt_id
            payments = get_debt_payments(session, debt_id)
            clear_state(chat_id)
            send_message(chat_id, f"Платёж обновлён. Остаток пересчитан.", build_debt_history_keyboard(debt_id, payments))
        else:
            send_message(chat_id, "Введите положительную сумму.", build_cancel_keyboard())
        return


def _fsm_goal_edit(chat_id, session, state, trimmed):
    step = state.get("step", "")
    gid = state["payload"].get("goal_id", "")
    field = state["payload"].get("field", "")
    g = get_goal(session, gid)
    if not g:
        clear_state(chat_id)
        send_message(chat_id, "Цель не найдена.", build_main_menu_keyboard())
        return
    if step != "value" or not field:
        return
    if field == "name":
        new_val = trimmed.strip()
        if new_val:
            old_v = str(g.name)
            if update_goal(session, gid, name=new_val):
                log_audit(session, chat_id, "goal", gid, "update", "name", old_v, new_val)
            clear_state(chat_id)
            send_message(chat_id, f"Название: {new_val}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите название.", build_cancel_keyboard())
        return
    if field == "target_amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt > 0:
            old_v = str(g.target_amount)
            if update_goal(session, gid, target_amount=amt):
                log_audit(session, chat_id, "goal", gid, "update", "target_amount", old_v, str(amt))
            clear_state(chat_id)
            send_message(chat_id, f"Цель: {amt} руб.", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите положительное число.", build_cancel_keyboard())
        return
    if field == "current_amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt >= 0:
            old_v = str(g.current_amount or 0)
            if update_goal(session, gid, current_amount=amt):
                log_audit(session, chat_id, "goal", gid, "update", "current_amount", old_v, str(amt))
            clear_state(chat_id)
            send_message(chat_id, f"Текущее: {amt} руб.", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите неотрицательное число.", build_cancel_keyboard())
        return
    if field == "deadline":
        date_val = trimmed.strip()[:10] if trimmed.strip() else ""
        if not date_val or (len(date_val) >= 8 and date_val.replace("-", "").replace(".", "").isdigit()):
            old_v = str(g.deadline or "")
            if update_goal(session, gid, deadline=date_val or ""):
                log_audit(session, chat_id, "goal", gid, "update", "deadline", old_v, date_val or "")
            clear_state(chat_id)
            send_message(chat_id, f"Срок: {date_val or 'сброшен'}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Формат: YYYY-MM-DD или пусто", build_cancel_keyboard())
        return
    if field == "priority":
        try:
            pri = int(float(trimmed.replace(" ", "").replace(",", ".")))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        old_v = str(g.priority or 0)
        if update_goal(session, gid, priority=pri):
            log_audit(session, chat_id, "goal", gid, "update", "priority", old_v, str(pri))
        clear_state(chat_id)
        send_message(chat_id, f"Приоритет: {pri}", build_main_menu_keyboard())
        return
    if field == "auto_fund_percent":
        try:
            pct = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if pct >= 0:
            old_v = str(g.auto_fund_percent or 0)
            if update_goal(session, gid, auto_fund_percent=pct):
                log_audit(session, chat_id, "goal", gid, "update", "auto_fund_percent", old_v, str(pct))
            clear_state(chat_id)
            send_message(chat_id, f"Авто %: {pct}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите неотрицательное число.", build_cancel_keyboard())
        return
    if field == "auto_fund_amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt >= 0:
            old_v = str(g.auto_fund_amount or 0)
            if update_goal(session, gid, auto_fund_amount=amt):
                log_audit(session, chat_id, "goal", gid, "update", "auto_fund_amount", old_v, str(amt))
            clear_state(chat_id)
            send_message(chat_id, f"Авто сумма: {amt}", build_main_menu_keyboard())
        else:
            send_message(chat_id, "Введите неотрицательное число.", build_cancel_keyboard())
        return


def _fsm_goal_transfer_amount(chat_id, session, state, trimmed):
    try:
        amt = float(trimmed.replace(" ", "").replace(",", "."))
    except ValueError:
        send_message(chat_id, "Введите число:", build_cancel_keyboard())
        return
    if amt <= 0:
        send_message(chat_id, "Введите положительное число.", build_cancel_keyboard())
        return
    from_id = state["payload"].get("from_goal_id", "")
    to_id = state["payload"].get("to_goal_id", "")
    if transfer_between_goals(session, from_id, to_id, amt):
        log_audit(session, chat_id, "goal", from_id, "update", "transfer", str(amt), to_id)
        from_g = get_goal(session, from_id)
        to_g = get_goal(session, to_id)
        clear_state(chat_id)
        msg = f"Перевод {int(amt)} руб. из «{from_g.name if from_g else ''}» в «{to_g.name if to_g else ''}»"
        send_message(chat_id, msg, build_main_menu_keyboard())
    else:
        from_g = get_goal(session, from_id)
        avail = from_g.current_amount if from_g else 0
        send_message(chat_id, f"Ошибка: недостаточно средств (доступно {int(avail)} руб.)", build_cancel_keyboard())


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


def _fsm_tpl_edit(chat_id, session, state, trimmed):
    tpl_id = state["payload"].get("tpl_id", "")
    field = state["payload"].get("field", "")
    t = get_template(session, tpl_id)
    if not t:
        clear_state(chat_id)
        send_message(chat_id, "Шаблон не найден.", build_main_menu_keyboard())
        return
    if field == "name":
        new_val = trimmed.strip()
        if new_val:
            old_v = str(t.name)
            if update_template(session, tpl_id, name=new_val):
                log_audit(session, chat_id, "template", tpl_id, "update", "name", old_v, new_val)
            clear_state(chat_id)
            templates = get_templates(session)
            send_message(chat_id, f"Название: {new_val}", build_templates_keyboard(templates))
        else:
            send_message(chat_id, "Введите название.", build_cancel_keyboard())
        return
    if field == "amount":
        try:
            amt = float(trimmed.replace(" ", "").replace(",", "."))
        except ValueError:
            send_message(chat_id, "Введите число:", build_cancel_keyboard())
            return
        if amt > 0:
            old_v = str(t.amount)
            if update_template(session, tpl_id, amount=amt):
                log_audit(session, chat_id, "template", tpl_id, "update", "amount", old_v, str(amt))
            clear_state(chat_id)
            templates = get_templates(session)
            send_message(chat_id, f"Сумма: {amt} руб.", build_templates_keyboard(templates))
        else:
            send_message(chat_id, "Введите положительное число.", build_cancel_keyboard())
        return


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


def _fsm_config_edit(chat_id, session, state, trimmed):
    param = state["payload"].get("param", "")
    if not param:
        clear_state(chat_id)
        send_message(chat_id, "Ошибка.", build_settings_keyboard())
        return
    set_config_param(session, param, trimmed.strip())
    log_audit(session, chat_id, "config", param, "update", None, None, trimmed.strip())
    clear_state(chat_id)
    send_message(chat_id, f"{param} = {trimmed.strip()}", build_settings_keyboard())


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


def _import_add_row(chat_id, session, r: dict, exclude_budget: bool):
    """Add single row from import to Finance. Store amounts as positive."""
    from services.excel_import import get_entry_type_from_amount
    date_str = r.get("date", "")[:10]
    amount_raw = r.get("amount", 0)
    entry_type = get_entry_type_from_amount(amount_raw)
    amount = abs(float(amount_raw))
    category = _map_bank_category_to_bot(session, r.get("category_bank", "Прочее"))
    comment = (r.get("description") or "")[:200]
    add_finance_entry(
        session, date_str, entry_type, amount, category, comment,
        exclude_from_budget=exclude_budget,
    )


def _send_import_page(chat_id, session, rows: list, p: dict, pending: set):
    """Send current page of import rows."""
    from bot.keyboards import build_import_rows_keyboard
    pending_list = sorted(pending)
    start_idx = min(p.get("start_idx", 0), max(0, len(pending_list) - 1))
    if not pending_list:
        clear_state(chat_id)
        added = len(p.get("added", []))
        skipped = len(p.get("skipped", []))
        send_message(chat_id, f"Импорт завершён. Добавлено: {added}, пропущено: {skipped}.", build_settings_keyboard())
        return
    lines = ["Выберите: + добавить, - пропустить"]
    pending_list = sorted(pending)
    for idx in pending_list[start_idx : start_idx + 5]:
        if idx >= len(rows):
            continue
        r = rows[idx]
        dup = has_finance_duplicate(session, r.get("date", ""), abs(float(r.get("amount", 0))))
        suffix = " (дубликат)" if dup else ""
        desc = (r.get("description") or "")[:60]
        lines.append(f"{r.get('date','')} {int(r.get('amount',0))} {r.get('category_bank','')}{suffix}\n  {desc}")
    msg = "\n".join(lines) if lines else "Нет операций."
    send_message(chat_id, msg, build_import_rows_keyboard(rows, start_idx, pending))


def _map_bank_category_to_bot(session, bank_cat: str) -> str:
    """Map bank category to bot category. Config key: CategoryMap:BankCat -> BotCat."""
    from db.repositories import get_config_param
    mapped = get_config_param(session, f"CategoryMap:{bank_cat}")
    if mapped:
        return mapped
    if bank_cat in EXPENSE_CATEGORIES:
        return bank_cat
    return "Прочее"


def _handle_import_excel_document(chat_id, session, state, message):
    import tempfile
    import os
    from services.excel_import import parse_alfa_bank, get_entry_type_from_amount
    from bot.keyboards import build_import_exclude_budget_keyboard

    doc = message.get("document", {})
    file_id = doc.get("file_id")
    file_name = (doc.get("file_name") or "").lower()
    if not file_id or not (file_name.endswith(".xlsx") or file_name.endswith(".xls")):
        send_message(chat_id, "Отправьте файл Excel (.xlsx).", build_cancel_keyboard())
        return

    fd, path = tempfile.mkstemp(suffix=".xlsx")
    try:
        os.close(fd)
        if not download_file(file_id, path):
            send_message(chat_id, "Не удалось скачать файл.", build_settings_keyboard())
            return
        rows = parse_alfa_bank(path)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass

    if not rows:
        clear_state(chat_id)
        send_message(chat_id, "В файле нет операций или формат не поддерживается.", build_settings_keyboard())
        return

    set_state(chat_id, "import_excel_confirm", "exclude_choice", {
        "rows": rows,
        "exclude_budget": None,
        "added": [],
        "skipped": [],
        "start_idx": 0,
    })
    send_message(chat_id, f"Найдено {len(rows)} операций. Исключить импортированные из бюджета?", build_import_exclude_budget_keyboard())


def _fsm_import_excel_confirm(chat_id, session, state, trimmed):
    """Text handler for import - cancel only."""
    if trimmed and trimmed.lower() in ("отмена", "cancel"):
        clear_state(chat_id)
        send_message(chat_id, "Импорт отменён.", build_settings_keyboard())


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
    if data == "help_edit":
        _handle_help_edit(chat_id)
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
            send_message(chat_id, "Шаблонов нет.", _inline_keyboard([[_btn("Добавить шаблон", "tpl_add")], [_btn("Назад", "cmd_help")]]))
        return
    if data == "cmd_settings":
        send_message(chat_id, "Настройки.", build_settings_keyboard())
        return
    if data == "import_excel":
        set_state(chat_id, "import_excel_wait_file", "0", {})
        send_message(chat_id, "Отправьте файл Excel (выписка Альфа-Банка).", build_cancel_keyboard())
        return
    if data in ("import_exclude_yes", "import_exclude_no"):
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "import_excel_confirm":
            excl = data == "import_exclude_yes"
            p = state.get("payload", {})
            rows = p.get("rows", [])
            p["exclude_budget"] = excl
            p["added"] = p.get("added", [])
            p["skipped"] = p.get("skipped", [])
            p["start_idx"] = 0
            pending = set(range(len(rows))) - set(p["added"]) - set(p["skipped"])
            set_state(chat_id, "import_excel_confirm", "rows", p)
            _send_import_page(chat_id, session, rows, p, pending)
        return
    if data.startswith("import_add_") or data.startswith("import_skip_"):
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "import_excel_confirm":
            idx = int(data.split("_")[-1])
            p = state.get("payload", {})
            rows = p.get("rows", [])
            if idx < 0 or idx >= len(rows):
                return
            r = rows[idx]
            if data.startswith("import_add_"):
                _import_add_row(chat_id, session, r, p.get("exclude_budget", False))
                p["added"] = p.get("added", []) + [idx]
            else:
                p["skipped"] = p.get("skipped", []) + [idx]
            p["rows"] = rows
            pending = set(range(len(rows))) - set(p["added"]) - set(p["skipped"])
            set_state(chat_id, "import_excel_confirm", "rows", p)
            _send_import_page(chat_id, session, rows, p, pending)
        return
    if data.startswith("import_page_"):
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "import_excel_confirm":
            start_idx = int(data.split("_")[-1])
            p = state.get("payload", {})
            rows = p.get("rows", [])
            pending = set(range(len(rows))) - set(p["added"]) - set(p["skipped"])
            p["start_idx"] = max(0, start_idx)
            set_state(chat_id, "import_excel_confirm", "rows", p)
            _send_import_page(chat_id, session, rows, p, pending)
        return
    if data == "import_done":
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "import_excel_confirm":
            p = state.get("payload", {})
            added = len(p.get("added", []))
            skipped = len(p.get("skipped", []))
            clear_state(chat_id)
            send_message(chat_id, f"Импорт завершён. Добавлено: {added}, пропущено: {skipped}.", build_settings_keyboard())
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
    if data == "cmd_back":
        state = get_state(chat_id)
        back_data = (state.get("payload") or {}).get("back_data") if state else None
        clear_state(chat_id)
        if back_data:
            _dispatch_callback(chat_id, back_data, session)
        else:
            send_message(chat_id, "Главное меню.", build_main_menu_keyboard())
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
    if data == "worklog_history":
        send_message(chat_id, "За какой период?", build_worklog_period_keyboard())
        return
    if data == "worklog_add_past":
        set_state(chat_id, "worklog_add_past", "dates", {})
        send_message(chat_id, "Введите даты полной отработки (8 ч). Форматы:\n• 11-13 — дни текущего месяца\n• 11 12 13 — перечисление\n• 2026-03-11 2026-03-12 — полные даты", build_cancel_keyboard())
        return
    if data.startswith("worklog_period_"):
        period = data.replace("worklog_period_", "")
        today = calc_today()
        if period == "today":
            start, end = today, today
        elif period == "week":
            from datetime import datetime, timedelta
            dt = datetime.strptime(today[:10], "%Y-%m-%d")
            start = (dt - timedelta(days=6)).strftime("%Y-%m-%d")
            end = today
        else:
            start, end = today[:7] + "-01", today
        entries = get_work_log_for_period(session, start, end, "Main")
        if not entries:
            send_message(chat_id, "Записей нет.", build_main_work_keyboard())
        else:
            lines = [f"Учёт за {start}–{end}:"]
            for e in entries:
                lines.append(f"  {e.date}: {e.hours_worked}ч {e.status}")
            send_message(chat_id, "\n".join(lines), build_worklog_list_keyboard(entries))
        return
    if data.startswith("worklog_edit_"):
        wl_id = data.replace("worklog_edit_", "")
        w = get_work_log(session, wl_id)
        if w:
            set_state(chat_id, "worklog_edit", "value", {"wl_id": wl_id, "field": "combined"})
            send_message(chat_id, f"Редактирование: {w.date} {w.hours_worked}ч {w.status}\nВведите: часы, статус (Work/Sick/WeekendWork). Пример: 6 Work", build_cancel_keyboard())
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
    if data == "orders_list":
        send_message(chat_id, "За какой период?", build_orders_period_keyboard())
        return
    if data == "orders_add_past":
        set_state(chat_id, "orders_add_past", "orders", {})
        send_message(chat_id, "Введите заказы. Каждая строка: дата описание сумма.\nПримеры:\n• 11 Доставка 1500\n• 12 Ремонт 3000\n• 2026-03-13 Консультация 500", build_cancel_keyboard())
        return
    if data.startswith("orders_period_"):
        period = data.replace("orders_period_", "")
        today = calc_today()
        from datetime import datetime, timedelta
        if period == "yesterday":
            start = end = (datetime.strptime(today[:10], "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        elif period == "week":
            dt = datetime.strptime(today[:10], "%Y-%m-%d")
            start = (dt - timedelta(days=6)).strftime("%Y-%m-%d")
            end = today
        else:
            start = today[:7] + "-01"
            end = today
        orders = get_orders_for_period(session, start, end)
        if not orders:
            send_message(chat_id, f"Заказов за {start}–{end} нет.", build_second_job_keyboard())
        else:
            total = sum(o.amount for o in orders)
            lines = [f"Заказы за {start}–{end} (итого {int(total)} руб.):"]
            for o in orders:
                lines.append(f"  {o.date}: {o.description or ''} {int(o.amount)} руб.")
            send_message(chat_id, "\n".join(lines), build_orders_list_keyboard(orders))
        return
    if data.startswith("order_edit_"):
        oid = data.replace("order_edit_", "")
        o = get_order(session, oid)
        if o:
            set_state(chat_id, "order_edit", "value", {"order_id": oid, "field": "combined"})
            send_message(chat_id, f"Редактирование: {o.date} {o.description} {o.amount}\nВведите: дата, описание, сумма. Пример: 2024-03-15 Доставка 1500", build_cancel_keyboard())
        return
    if data.startswith("order_del_"):
        oid = data.replace("order_del_", "")
        if delete_order(session, oid):
            log_audit(session, chat_id, "order", oid, "delete", None, None, None)
        send_message(chat_id, "Заказ удалён.", build_second_job_keyboard())
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
    if data == "budget_bulk":
        month_year = calc_today()[:7]
        set_state(chat_id, "budget_bulk", "0", {"month_year": month_year})
        send_message(chat_id, f"Лимиты на {month_year}. Введите пары «категория: сумма», по одной на строку. Пример:\nЕда: 15000\nТранспорт: 5000", build_cancel_keyboard())
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
    if data.startswith("goal_detail_"):
        gid = data.replace("goal_detail_", "")
        g = get_goal(session, gid)
        if g:
            from services.goals import get_goal_icon
            icon = get_goal_icon(getattr(g, "goal_type", "other") or "other")
            pct = int(100 * g.current_amount / g.target_amount) if g.target_amount else 0
            dl = f" до {g.deadline}" if g.deadline else ""
            msg = f"{icon} {g.name}\n{int(g.current_amount)}/{int(g.target_amount)} ({pct}%){dl}"
            send_message(chat_id, msg, build_goal_detail_keyboard(gid))
        return
    if data.startswith("goal_fund_"):
        gid = data.replace("goal_fund_", "")
        if get_goal(session, gid):
            set_state(chat_id, "goals_fund_amount", "0", {"goal_id": gid})
            send_message(chat_id, "Сумма пополнения (руб):", build_cancel_keyboard())
        return
    if data.startswith("goal_edit_"):
        rest = data.replace("goal_edit_", "")
        if "_" in rest:
            parts = rest.split("_", 1)
            field, gid = parts[0], parts[1]
            g = get_goal(session, gid)
            if not g:
                return
            if field == "name":
                set_state(chat_id, "goal_edit", "value", {"goal_id": gid, "field": "name"})
                send_message(chat_id, f"Название (было: {g.name}):", build_cancel_keyboard())
                return
            if field == "target":
                set_state(chat_id, "goal_edit", "value", {"goal_id": gid, "field": "target_amount"})
                send_message(chat_id, f"Целевая сумма (было: {g.target_amount}):", build_cancel_keyboard())
                return
            if field == "current":
                set_state(chat_id, "goal_edit", "value", {"goal_id": gid, "field": "current_amount"})
                send_message(chat_id, f"Текущая сумма (было: {g.current_amount}):", build_cancel_keyboard())
                return
            if field == "deadline":
                set_state(chat_id, "goal_edit", "value", {"goal_id": gid, "field": "deadline"})
                send_message(chat_id, f"Срок YYYY-MM-DD (было: {g.deadline or '-'}):", build_cancel_keyboard())
                return
            if field == "priority":
                set_state(chat_id, "goal_edit", "value", {"goal_id": gid, "field": "priority"})
                send_message(chat_id, f"Приоритет (было: {g.priority or 0}):", build_cancel_keyboard())
                return
            if field == "type":
                set_state(chat_id, "goal_edit", "type_select", {"goal_id": gid})
                send_message(chat_id, "Тип цели:", build_goal_type_keyboard_for_edit(gid))
                return
            if field == "autopct":
                set_state(chat_id, "goal_edit", "value", {"goal_id": gid, "field": "auto_fund_percent"})
                send_message(chat_id, f"Авто % от дохода (было: {g.auto_fund_percent or 0}):", build_cancel_keyboard())
                return
            if field == "autoamt":
                set_state(chat_id, "goal_edit", "value", {"goal_id": gid, "field": "auto_fund_amount"})
                send_message(chat_id, f"Авто сумма (было: {g.auto_fund_amount or 0}):", build_cancel_keyboard())
                return
        else:
            gid = data.replace("goal_edit_", "")
            g = get_goal(session, gid)
            if g:
                set_state(chat_id, "goal_edit", "field_select", {"goal_id": gid, "back_data": f"goal_detail_{gid}"})
                txt = f"Редактирование: {g.name}"
                send_message(chat_id, txt, build_goal_edit_field_keyboard(gid))
        return
    if data.startswith("gtype_edit_"):
        rest = data.replace("gtype_edit_", "")
        parts = rest.rsplit("_", 1)
        if len(parts) == 2:
            gtype, gid = parts
            gtype_map = {"vacation": "vacation", "tech": "tech", "cushion": "cushion", "purchase": "purchase", "other": "other"}
            gt = gtype_map.get(gtype, "other")
            if update_goal(session, gid, goal_type=gt):
                log_audit(session, chat_id, "goal", gid, "update", "goal_type", None, gt)
            g = get_goal(session, gid)
            if g:
                set_state(chat_id, "goal_edit", "field_select", {"goal_id": gid, "back_data": f"goal_detail_{gid}"})
                send_message(chat_id, f"Тип: {gt}. Редактирование: {g.name}", build_goal_edit_field_keyboard(gid))
        return
    if data.startswith("goal_transfer_"):
        if data.startswith("goal_transfer_to_"):
            rest = data.replace("goal_transfer_to_", "")
            parts = rest.split("_", 1)
            if len(parts) == 2:
                to_id, from_id = parts[0], parts[1]
                set_state(chat_id, "goal_transfer_amount", "0", {"from_goal_id": from_id, "to_goal_id": to_id})
                send_message(chat_id, "Сумма перевода (руб):", build_cancel_keyboard())
        else:
            from_id = data.replace("goal_transfer_", "")
            g_from = get_goal(session, from_id)
            if not g_from:
                return
            goals = [x for x in get_active_goals(session) if x.id != from_id]
            if not goals:
                send_message(chat_id, "Нет других целей для перевода.", build_goal_detail_keyboard(from_id))
                return
            send_message(chat_id, "Куда перевести?", build_goal_transfer_target_keyboard(goals, from_id))
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
    if data.startswith("debt_kind_"):
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "debts_add":
            kind = data.replace("debt_kind_", "")
            set_state(chat_id, "debts_add", "payment_mode", {**state.get("payload", {}), "debt_kind": kind})
            send_message(chat_id, "Как задать платёж?", build_debt_payment_mode_keyboard())
        return
    if data == "debt_pmode_calc":
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "debts_add":
            set_state(chat_id, "debts_add", "months", state.get("payload", {}))
            send_message(chat_id, "Срок в месяцах:", build_cancel_keyboard())
        return
    if data == "debt_pmode_enter":
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "debts_add":
            set_state(chat_id, "debts_add", "monthly_payment", state.get("payload", {}))
            send_message(chat_id, "Сумма платежа из банка (руб):", build_cancel_keyboard())
        return
    if data.startswith("debt_ptype_"):
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "debts_add":
            from services.debt_calc import calc_annuity_payment, calc_fixed_first_payment
            ptype = "annuity" if "annuity" in data else "fixed"
            p = {**state.get("payload", {}), "payment_type": ptype}
            amt = p.get("amount", 0)
            rate = p.get("interest", 0)
            months = p.get("months", 12)
            if ptype == "annuity":
                calc_pmt = calc_annuity_payment(amt, rate, months)
            else:
                calc_pmt = calc_fixed_first_payment(amt, rate, months)
            set_state(chat_id, "debts_add", "confirm_payment", {**p, "calc_payment": calc_pmt})
            send_message(chat_id, f"Примерный платёж: {int(calc_pmt)} руб.", build_debt_confirm_payment_keyboard(calc_pmt))
        return
    if data == "debt_confirm_yes":
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "debts_add":
            p = state.get("payload", {})
            pmt = p.get("calc_payment", 0)
            set_state(chat_id, "debts_add", "cycle", {**p, "monthly_payment": pmt})
            send_message(chat_id, "Интервал платежей:", build_debt_cycle_keyboard())
        return
    if data == "debt_confirm_custom":
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "debts_add":
            set_state(chat_id, "debts_add", "monthly_payment", state.get("payload", {}))
            send_message(chat_id, "Введите сумму платежа (руб):", build_cancel_keyboard())
        return
    if data.startswith("debt_cycle_"):
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "debts_add":
            cycle = "biweekly" if "biweekly" in data else "monthly"
            set_state(chat_id, "debts_add", "next_payment_date", {**state.get("payload", {}), "payment_cycle": cycle})
            send_message(chat_id, "Дата следующего платежа (YYYY-MM-DD):", build_cancel_keyboard())
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
                f"Платёж: {int(debt.monthly_payment or 0)} руб.\n"
                f"След. платёж: {getattr(debt, 'next_payment_date', None) or 'не указан'}\n"
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
            send_message(chat_id, "Платежей нет. Добавить платёж задним числом?", build_debt_history_keyboard(debt_id, []))
            return
        lines = ["История платежей (кнопки Редактировать/Удалить):"]
        for p in payments:
            lines.append(f"  {p.date}: {int(p.amount)} руб. {p.comment or ''}")
        send_message(chat_id, "\n".join(lines), build_debt_history_keyboard(debt_id, payments))
        return
    if data.startswith("debt_edit_"):
        rest = data.replace("debt_edit_", "")
        if "_" in rest:
            parts = rest.split("_", 1)
            field, debt_id = parts[0], parts[1]
            debt = get_debt(session, debt_id)
            if not debt:
                return
            if field == "counterparty":
                set_state(chat_id, "debt_edit", "value", {"debt_id": debt_id, "field": "counterparty", "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, f"Контрагент (было: {debt.counterparty}):", build_cancel_keyboard())
                return
            if field == "amount":
                set_state(chat_id, "debt_edit", "value", {"debt_id": debt_id, "field": "original_amount", "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, f"Исходная сумма (было: {debt.original_amount}):", build_cancel_keyboard())
                return
            if field == "remaining":
                set_state(chat_id, "debt_remaining_comment", "0", {"debt_id": debt_id, "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, f"Новый остаток (сейчас {debt.remaining_amount}). Комментарий (обязательно):", build_cancel_keyboard())
                return
            if field == "rate":
                set_state(chat_id, "debt_edit", "value", {"debt_id": debt_id, "field": "interest_rate", "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, f"Ставка % (было: {debt.interest_rate or 0}):", build_cancel_keyboard())
                return
            if field == "payment":
                set_state(chat_id, "debt_edit", "value", {"debt_id": debt_id, "field": "monthly_payment", "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, f"Сумма платежа (было: {debt.monthly_payment or 0}):", build_cancel_keyboard())
                return
            if field == "cycle":
                set_state(chat_id, "debt_edit", "cycle_select", {"debt_id": debt_id, "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, "Цикл платежей:", build_debt_cycle_edit_keyboard(debt_id))
                return
            if field == "next":
                set_state(chat_id, "debt_edit", "value", {"debt_id": debt_id, "field": "next_payment_date", "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, f"Дата след. платежа (было: {debt.next_payment_date or '-'}):", build_cancel_keyboard())
                return
            if field == "due":
                set_state(chat_id, "debt_edit", "value", {"debt_id": debt_id, "field": "due_date", "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, f"Срок (YYYY-MM-DD, было: {debt.due_date or '-'}):", build_cancel_keyboard())
                return
            if field == "kind":
                set_state(chat_id, "debt_edit", "kind_select", {"debt_id": debt_id, "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, "Тип долга:", build_debt_kind_edit_keyboard(debt_id))
                return
        else:
            debt_id = data.replace("debt_edit_", "")
            debt = get_debt(session, debt_id)
            if debt:
                set_state(chat_id, "debt_edit", "field_select", {"debt_id": debt_id, "back_data": f"debt_detail_{debt_id}"})
                txt = f"Редактирование: {debt.counterparty}, остаток {int(debt.remaining_amount)}"
                send_message(chat_id, txt, build_debt_edit_field_keyboard(debt_id))
        return
    if data.startswith("debt_cycle_val_"):
        rest = data.replace("debt_cycle_val_", "")
        parts = rest.rsplit("_", 1)
        if len(parts) == 2:
            cycle, debt_id = parts
            if update_debt(session, debt_id, payment_cycle=cycle):
                log_audit(session, chat_id, "debt", debt_id, "update", "payment_cycle", None, cycle)
            debt = get_debt(session, debt_id)
            if debt:
                set_state(chat_id, "debt_edit", "field_select", {"debt_id": debt_id, "back_data": f"debt_detail_{debt_id}"})
                send_message(chat_id, f"Цикл: {cycle}. Редактирование: {debt.counterparty}", build_debt_edit_field_keyboard(debt_id))
        return
    if data.startswith("debt_kind_val_"):
        rest = data.replace("debt_kind_val_", "")
        parts = rest.rsplit("_", 1)
        if len(parts) == 2:
            kind, debt_id = parts
            debt = get_debt(session, debt_id)
            if debt:
                kind_labels = {"credit": "Кредит", "installment": "Рассрочка", "card": "Кредитная карта", "overdraft": "Овердрафт"}
                label = kind_labels.get(kind, kind)
                changed = (debt.debt_kind or "credit") != kind
                if update_debt(session, debt_id, debt_kind=kind):
                    log_audit(session, chat_id, "debt", debt_id, "update", "debt_kind", None, kind)
                debt = get_debt(session, debt_id)
                set_state(chat_id, "debt_edit", "field_select", {"debt_id": debt_id, "back_data": f"debt_detail_{debt_id}"})
                if changed:
                    send_message(chat_id, f"Тип: {label}. Редактирование: {debt.counterparty}", build_debt_edit_field_keyboard(debt_id))
                else:
                    send_message(chat_id, f"Тип без изменений: {label}. Редактирование: {debt.counterparty}", build_debt_edit_field_keyboard(debt_id))
        return
    if data.startswith("debt_pay_edit_"):
        pid = data.replace("debt_pay_edit_", "")
        p = get_debt_payment(session, pid)
        if p:
            set_state(chat_id, "debt_payment_edit", "amount", {"payment_id": pid, "debt_id": p.debt_id})
            send_message(chat_id, f"Новая сумма (было {p.amount}), дата (было {p.date}):", build_cancel_keyboard())
        return
    if data.startswith("debt_pay_del_"):
        pid = data.replace("debt_pay_del_", "")
        p = get_debt_payment(session, pid)
        if p:
            if delete_debt_payment(session, pid):
                log_audit(session, chat_id, "debt", p.debt_id, "update", "payment_deleted", str(p.amount), None)
            debt = get_debt(session, p.debt_id)
            payments = get_debt_payments(session, p.debt_id)
            send_message(chat_id, "Платёж удалён. История:", build_debt_history_keyboard(p.debt_id, payments))
        return
    if data.startswith("debt_pay_add_"):
        debt_id = data.replace("debt_pay_add_", "")
        set_state(chat_id, "debt_pay_add", "amount", {"debt_id": debt_id})
        send_message(chat_id, "Сумма платежа (руб), дата (YYYY-MM-DD или пусто = сегодня):", build_cancel_keyboard())
        return

    # Subscriptions
    if data == "subs_list":
        _handle_subs_list(chat_id, session)
        return
    if data == "subs_add":
        set_state(chat_id, "subs_add", "name", {})
        send_message(chat_id, "Название подписки:", build_cancel_keyboard())
        return
    if data == "subs_paused":
        paused = get_inactive_subscriptions(session)
        if not paused:
            send_message(chat_id, "Приостановленных подписок нет.", build_subscriptions_keyboard())
        else:
            send_message(chat_id, "Приостановленные:", build_subs_select_keyboard(paused))
        return
    if data == "subs_overdue":
        overdue = get_overdue_subscriptions(session)
        if not overdue:
            send_message(chat_id, "Просроченных подписок нет.", build_subscriptions_keyboard())
        else:
            send_message(chat_id, "Просроченные подписки:", build_subs_select_keyboard(overdue))
        return
    if data.startswith("subs_detail_"):
        sub_id = data.replace("subs_detail_", "")
        s = get_subscription(session, sub_id)
        if s:
            msg = f"{s.name}\n{int(s.amount)} руб. / {s.cycle}, след. {s.next_date}\nКатегория: {s.category or 'Прочее'}"
            send_message(chat_id, msg, build_subs_detail_keyboard(sub_id, s.is_active))
        return
    if data.startswith("subs_pause_"):
        sub_id = data.replace("subs_pause_", "")
        if update_subscription(session, sub_id, is_active=False):
            log_audit(session, chat_id, "subscription", sub_id, "update", "is_active", "True", "False")
        s = get_subscription(session, sub_id)
        if s:
            send_message(chat_id, "Подписка приостановлена.", build_subs_detail_keyboard(sub_id, s.is_active))
        return
    if data.startswith("subs_resume_"):
        sub_id = data.replace("subs_resume_", "")
        if update_subscription(session, sub_id, is_active=True):
            log_audit(session, chat_id, "subscription", sub_id, "update", "is_active", "False", "True")
        s = get_subscription(session, sub_id)
        if s:
            send_message(chat_id, "Подписка возобновлена.", build_subs_detail_keyboard(sub_id, s.is_active))
        return
    if data.startswith("subs_delete_"):
        sub_id = data.replace("subs_delete_", "")
        set_state(chat_id, "subs_delete_confirm", "0", {"sub_id": sub_id})
        send_message(chat_id, "Удалить подписку полностью? Напишите ДА для подтверждения.", build_cancel_keyboard())
        return
    if data.startswith("subs_edit_"):
        rest = data.replace("subs_edit_", "")
        if "_" in rest:
            parts = rest.split("_", 1)
            field, sub_id = parts[0], parts[1]
            s = get_subscription(session, sub_id)
            if not s:
                return
            if field == "name":
                set_state(chat_id, "subs_edit", "value", {"sub_id": sub_id, "field": "name"})
                send_message(chat_id, f"Название (было: {s.name}):", build_cancel_keyboard())
                return
            if field == "amount":
                set_state(chat_id, "subs_edit", "value", {"sub_id": sub_id, "field": "amount"})
                send_message(chat_id, f"Сумма (было: {s.amount}):", build_cancel_keyboard())
                return
            if field == "cycle":
                set_state(chat_id, "subs_edit", "cycle_select", {"sub_id": sub_id})
                send_message(chat_id, "Цикл:", build_subs_cycle_keyboard(sub_id))
                return
            if field == "next":
                set_state(chat_id, "subs_edit", "value", {"sub_id": sub_id, "field": "next_date"})
                send_message(chat_id, f"Дата след. списания (было: {s.next_date}):", build_cancel_keyboard())
                return
            if field == "cat":
                set_state(chat_id, "subs_edit", "value", {"sub_id": sub_id, "field": "category"})
                send_message(chat_id, f"Категория (было: {s.category or 'Прочее'}):", build_expense_categories_keyboard())
                return
            if field == "remind":
                set_state(chat_id, "subs_edit", "value", {"sub_id": sub_id, "field": "remind_days_before"})
                send_message(chat_id, f"Напомин. за дней (было: {s.remind_days_before or 1}):", build_cancel_keyboard())
                return
            if field == "auto":
                new_val = not getattr(s, "auto_create_expense", False)
                update_subscription(session, sub_id, auto_create_expense=new_val)
                log_audit(session, chat_id, "subscription", sub_id, "update", "auto_create_expense", str(not new_val), str(new_val))
                s = get_subscription(session, sub_id)
                send_message(chat_id, f"Авто расход: {'да' if new_val else 'нет'}", build_subs_edit_field_keyboard(sub_id))
                return
            if field == "group":
                set_state(chat_id, "subs_edit", "group_select", {"sub_id": sub_id})
                send_message(chat_id, "Группа:", build_subs_group_keyboard(sub_id))
                return
        else:
            sub_id = data.replace("subs_edit_", "")
            s = get_subscription(session, sub_id)
            if s:
                set_state(chat_id, "subs_edit", "field_select", {"sub_id": sub_id, "back_data": f"subs_detail_{sub_id}"})
                send_message(chat_id, f"Редактирование: {s.name}", build_subs_edit_field_keyboard(sub_id))
        return
    if data.startswith("subs_cycle_"):
        rest = data.replace("subs_cycle_", "")
        if "_" in rest:
            cycle, sub_id = rest.rsplit("_", 1)
            if cycle in ("monthly", "weekly", "yearly") and sub_id:
                update_subscription(session, sub_id, cycle=cycle)
                log_audit(session, chat_id, "subscription", sub_id, "update", "cycle", None, cycle)
            s = get_subscription(session, sub_id)
            if s:
                send_message(chat_id, f"Цикл: {cycle}", build_subs_edit_field_keyboard(sub_id))
        return
    if data.startswith("subs_group_"):
        rest = data.replace("subs_group_", "")
        parts = rest.rsplit("_", 1)
        if len(parts) == 2:
            group, sub_id = parts[0], parts[1]
            if update_subscription(session, sub_id, group=group):
                log_audit(session, chat_id, "subscription", sub_id, "update", "group", None, group)
            s = get_subscription(session, sub_id)
            if s:
                send_message(chat_id, f"Группа: {group}", build_subs_edit_field_keyboard(sub_id))
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
            _show_finance_edit_field_select(chat_id, session, fid, entry)
        return
    if data.startswith("edit_fin_field_"):
        rest = data.replace("edit_fin_field_", "")
        parts = rest.rsplit("_", 1)
        if len(parts) != 2:
            return
        field, fid = parts
        entry = get_finance_by_id(session, fid)
        if not entry:
            return
        if field == "excl":
            new_val = not getattr(entry, "exclude_from_budget", False)
            update_finance_entry(session, fid, exclude_from_budget=new_val)
            log_audit(session, chat_id, "finance", fid, "update", "exclude_from_budget", str(not new_val), str(new_val))
            entry = get_finance_by_id(session, fid)
            set_state(chat_id, "finance_edit", "field_select", {"finance_id": fid, "back_data": "cmd_history"})
            status = "Исключено из бюджета. " if new_val else "Учитывается в бюджете. "
            txt = status + (f"Редактирование: {entry.date} {entry.category} {entry.amount} руб." if entry else "")
            send_message(chat_id, txt, build_finance_edit_field_keyboard(fid))
            return
        if field == "amount":
            set_state(chat_id, "finance_edit", "value", {"finance_id": fid, "field": "amount", "back_data": "cmd_history"})
            send_message(chat_id, f"Новая сумма (было {entry.amount}):", build_cancel_keyboard())
            return
        if field == "date":
            set_state(chat_id, "finance_edit", "value", {"finance_id": fid, "field": "date", "back_data": "cmd_history"})
            send_message(chat_id, f"Новая дата (было {entry.date}):", build_cancel_keyboard())
            return
        if field == "cat":
            set_state(chat_id, "finance_edit", "value", {"finance_id": fid, "field": "category", "back_data": "cmd_history"})
            send_message(chat_id, f"Новая категория (было {entry.category}):", build_expense_categories_keyboard())
            return
        if field == "comment":
            set_state(chat_id, "finance_edit", "value", {"finance_id": fid, "field": "comment", "back_data": "cmd_history"})
            send_message(chat_id, f"Новый комментарий (было: {entry.comment or '-'}):", build_cancel_keyboard())
            return
        if field == "type":
            set_state(chat_id, "finance_edit", "type_select", {"finance_id": fid, "back_data": "cmd_history"})
            send_message(chat_id, "Новый тип:", build_finance_type_keyboard(fid))
            return
        return
    if data.startswith("edit_fin_type_"):
        parts = data.replace("edit_fin_type_", "").rsplit("_", 1)
        if len(parts) == 2:
            ftype, fid = parts
            update_finance_entry(session, fid, entry_type=ftype)
            log_audit(session, chat_id, "finance", fid, "update", "type", None, ftype)
            entry = get_finance_by_id(session, fid)
            if entry:
                _show_finance_edit_field_select(chat_id, session, fid, entry)
        return
    if data.startswith("edit_fin_soft_del_"):
        fid = data.replace("edit_fin_soft_del_", "")
        set_state(chat_id, "finance_soft_delete_confirm", "0", {"finance_id": fid})
        send_message(chat_id, "Удалить запись (скрыть из отчётов)? Напишите ДА для подтверждения.", build_cancel_keyboard())
        return

    # Expense category selection
    if data.startswith("exp_cat_"):
        try:
            idx = int(data.replace("exp_cat_", ""))
        except ValueError:
            return
        if idx < 0 or idx >= len(EXPENSE_CATEGORIES):
            return
        cat = EXPENSE_CATEGORIES[idx]
        s = get_state(chat_id)
        if s and s.get("scenario") == "expense_cat" and s.get("payload", {}).get("amount") is not None:
            set_state(chat_id, "expense_comment", "0", {"amount": s["payload"]["amount"], "category": cat})
            send_message(chat_id, "Комментарий к расходу:", build_expense_comment_keyboard())
        elif s and s.get("scenario") == "tpl_add" and s.get("step") == "category":
            add_template(session, s["payload"]["name"], s["payload"]["amount"], cat)
            clear_state(chat_id)
            send_message(chat_id, "Шаблон добавлен.", build_main_menu_keyboard())
        elif s and s.get("scenario") == "finance_edit" and s.get("step") == "value" and s.get("payload", {}).get("field") == "category":
            fid = s["payload"].get("finance_id", "")
            entry = get_finance_by_id(session, fid)
            if entry:
                old_v = str(entry.category or "")
                if update_finance_entry(session, fid, category=cat):
                    log_audit(session, chat_id, "finance", fid, "update", "category", old_v, cat)
                    clear_state(chat_id)
                    send_message(chat_id, f"Категория: {cat}", build_main_menu_keyboard())
        elif s and s.get("scenario") == "tpl_edit" and s.get("step") == "value" and s.get("payload", {}).get("field") == "category":
            tpl_id = s["payload"].get("tpl_id", "")
            t = get_template(session, tpl_id)
            if t:
                old_v = str(t.category or "")
                if update_template(session, tpl_id, category=cat):
                    log_audit(session, chat_id, "template", tpl_id, "update", "category", old_v, cat)
                    clear_state(chat_id)
                    send_message(chat_id, f"Категория: {cat}", build_main_menu_keyboard())
        elif s and s.get("scenario") == "subs_edit" and s.get("step") == "value" and s.get("payload", {}).get("field") == "category":
            sub_id = s["payload"].get("sub_id", "")
            subs = get_subscription(session, sub_id)
            if subs:
                old_v = str(subs.category or "")
                if update_subscription(session, sub_id, category=cat):
                    log_audit(session, chat_id, "subscription", sub_id, "update", "category", old_v, cat)
                    clear_state(chat_id)
                    send_message(chat_id, f"Категория: {cat}", build_main_menu_keyboard())
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
    if data.startswith("tpl_edit_"):
        rest = data.replace("tpl_edit_", "")
        if "_" in rest:
            field, tpl_id = rest.split("_", 1)
            t = get_template(session, tpl_id)
            if not t:
                return
            if field == "name":
                set_state(chat_id, "tpl_edit", "value", {"tpl_id": tpl_id, "field": "name"})
                send_message(chat_id, f"Название (было: {t.name}):", build_cancel_keyboard())
                return
            if field == "amount":
                set_state(chat_id, "tpl_edit", "value", {"tpl_id": tpl_id, "field": "amount"})
                send_message(chat_id, f"Сумма (было: {t.amount}):", build_cancel_keyboard())
                return
            if field == "cat":
                set_state(chat_id, "tpl_edit", "value", {"tpl_id": tpl_id, "field": "category"})
                send_message(chat_id, f"Категория (было: {t.category}):", build_expense_categories_keyboard())
                return
        else:
            tpl_id = data.replace("tpl_edit_", "")
            t = get_template(session, tpl_id)
            if t:
                set_state(chat_id, "tpl_edit", "field_select", {"tpl_id": tpl_id, "back_data": "cmd_templates"})
                send_message(chat_id, f"Редактирование: {t.name} {int(t.amount)} руб.", build_tpl_edit_keyboard(tpl_id))
        return
    if data.startswith("tpl_del_"):
        tpl_id = data.replace("tpl_del_", "")
        if delete_template(session, tpl_id):
            log_audit(session, chat_id, "template", tpl_id, "delete", None, None, None)
        templates = get_templates(session)
        send_message(chat_id, "Шаблон удалён.", build_templates_keyboard(templates))
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
    if data == "settings_config":
        send_message(chat_id, "Параметры конфигурации:", build_config_params_keyboard())
        return
    if data == "settings_tags":
        tags = get_tags(session)
        if not tags:
            send_message(chat_id, "Тегов нет. Добавьте тег:", build_tags_keyboard([]))
        else:
            send_message(chat_id, "Теги (переименовать/удалить):", build_tags_keyboard(tags))
        return
    if data == "tag_add":
        set_state(chat_id, "tag_add", "0", {})
        send_message(chat_id, "Название тега:", build_cancel_keyboard())
        return
    if data.startswith("tag_edit_"):
        tag_id = data.replace("tag_edit_", "")
        set_state(chat_id, "tag_rename", "0", {"tag_id": tag_id})
        send_message(chat_id, "Новое название:", build_cancel_keyboard())
        return
    if data.startswith("tag_del_"):
        tag_id = data.replace("tag_del_", "")
        if delete_tag(session, tag_id):
            log_audit(session, chat_id, "tag", tag_id, "delete", None, None, None)
        tags = get_tags(session)
        send_message(chat_id, "Тег удалён.", build_tags_keyboard(tags))
        return
    if data == "settings_achievements":
        achievements = get_achievements(session)
        if not achievements:
            send_message(chat_id, "Достижений нет.", build_settings_keyboard())
        else:
            send_message(chat_id, "Достижения (сбросить = удалить для переразблокировки):", build_achievements_keyboard(achievements))
        return
    if data.startswith("ach_reset_"):
        aid = int(data.replace("ach_reset_", ""))
        if delete_achievement(session, aid):
            log_audit(session, chat_id, "achievement", str(aid), "delete", None, None, None)
        send_message(chat_id, "Достижение сброшено. Можно разблокировать заново.", build_settings_keyboard())
        return
    if data == "settings_calculations":
        calcs = get_calculations(session)
        if not calcs:
            send_message(chat_id, "Записей о начисленной/полученной ЗП нет.", build_settings_keyboard())
        else:
            lines = ["Расчёты ЗП (начислено/получено):"]
            for c in calcs[:5]:
                lines.append(f"  {c.period_start}–{c.period_end}: нач. {int(c.accrued_salary or 0)}, пол. {int(c.received_salary or 0)}, разница {int(c.difference or 0)}")
            send_message(chat_id, "\n".join(lines), build_calculations_keyboard(calcs))
        return
    if data.startswith("calc_edit_"):
        cid = int(data.replace("calc_edit_", ""))
        c = get_calculation(session, cid)
        if c:
            set_state(chat_id, "calc_edit", "0", {"calc_id": cid})
            send_message(chat_id, f"Редактирование: {c.period_start}–{c.period_end}\nВведите: начислено получено (через пробел)", build_cancel_keyboard())
        return
    if data == "edit_menu":
        send_message(chat_id, "Редактирование — выберите раздел:", build_edit_menu_keyboard())
        return
    if data == "finance_mass":
        set_state(chat_id, "finance_mass", "period", {})
        send_message(chat_id, "Выберите период:", build_mass_period_keyboard())
        return
    if data.startswith("mass_period_"):
        period = data.replace("mass_period_", "")
        from datetime import datetime, timedelta
        today = calc_today()
        if period == "week":
            start = (datetime.strptime(today[:10], "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")
        else:
            start = today[:7] + "-01"
        set_state(chat_id, "finance_mass", "category", {"period": period, "start": start, "end": today})
        send_message(chat_id, "Выберите категорию:", build_mass_category_keyboard())
        return
    if data.startswith("mass_cat_"):
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "finance_mass":
            cat_part = data.replace("mass_cat_", "")
            if cat_part == "all":
                cat = "all"
            elif cat_part.isdigit() and 0 <= int(cat_part) < len(EXPENSE_CATEGORIES):
                cat = EXPENSE_CATEGORIES[int(cat_part)]
            else:
                cat = "all"
            set_state(chat_id, "finance_mass", "action", {**state.get("payload", {}), "category": cat})
            send_message(chat_id, "Действие:", build_mass_action_keyboard())
        return
    if data.startswith("mass_action_"):
        action = data.replace("mass_action_", "")
        state = get_state_db(session, chat_id)
        if state and state.get("scenario") == "finance_mass":
            p = state.get("payload", {})
            act_type = "soft_delete" if action == "delete" else "exclude_from_budget"
            set_state(chat_id, "finance_mass_confirm", "0", {**p, "action": act_type})
            act_txt = "удалить" if action == "delete" else "исключить из бюджета"
            send_message(chat_id, f"Подтвердите: {act_txt} записи за {p.get('start','')}–{p.get('end','')} (категория: {p.get('category','все')}). Напишите ДА", build_cancel_keyboard())
        return
    if data.startswith("config_edit_"):
        param = data.replace("config_edit_", "")
        current = get_config_param(session, param) or ""
        set_state(chat_id, "config_edit", "0", {"param": param})
        param_label = next((l for p, l in CONFIG_PARAMS if p == param), param)
        send_message(chat_id, f"{param_label} (текущее: {current}):", build_cancel_keyboard())
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
    send_message(chat_id, "Выберите подписку:", build_subs_select_keyboard(subs))


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
    send_message(chat_id, msg, build_help_with_edit_keyboard())


def build_help_with_edit_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Как редактировать", "help_edit")],
        [_btn("Главное меню", "cmd_status")],
    ])


def _handle_help_edit(chat_id: int):
    msg = (
        "Как редактировать:\n\n"
        "• Финансы — История → выберите запись → сумма, дата, категория, комментарий, удалить\n"
        "• Долги — список → карточка → контрагент, сумма, ставка, платёж, дата, срок, остаток, платежи\n"
        "• Цели — список → карточка → название, цель, текущее, срок, приоритет, авто-пополнение, перевод\n"
        "• Подписки — список → карточка → название, сумма, дата, напоминание, пауза, удалить\n"
        "• Бюджет — настройка лимитов → по категориям или массово\n"
        "• WorkLog — за период → выберите запись\n"
        "• Заказы — за период → выберите заказ\n"
        "• Шаблоны — список → выберите шаблон\n"
        "• Массовые операции — История → Массовые операции (удалить/исключить за период)\n"
        "• Последний расход — /редактировать или «Редактировать последний»"
    )
    send_message(chat_id, msg, _inline_keyboard([[_btn("← Справка", "cmd_help")]]))


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
    send_message(chat_id, f"За вчера ({yesterday}): заказов {len(orders)}, сумма {int(total)} руб.", build_second_job_keyboard())


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
