"""Inline keyboards for Telegram bot."""
from typing import Any

EXPENSE_CATEGORIES = [
    "Еда",
    "Транспорт",
    "ЗП Выплата",
    "Жильё",
    "Здоровье",
    "Развлечения",
    "Прочее",
]


def _inline_keyboard(buttons: list[list[dict]]) -> dict:
    """Build inline_keyboard structure for Telegram API."""
    return {"inline_keyboard": buttons}


def _btn(text: str, callback_data: str) -> dict:
    return {"text": text, "callback_data": callback_data}


def build_main_work_keyboard() -> dict:
    return _inline_keyboard([
        [
            _btn("Полный (8ч)", "main_full"),
            _btn("Частично", "main_partial"),
        ],
        [
            _btn("Не работал", "main_none"),
            _btn("Выходной (работал)", "main_weekend"),
        ],
        [_btn("Больничный", "main_sick")],
    ])


def build_second_job_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Добавить заказ", "second_add")],
        [
            _btn("Нет доходов", "second_none"),
            _btn("Посмотреть статус", "second_status"),
        ],
    ])


def build_expense_categories_keyboard() -> dict:
    row = []
    keyboard = []
    for i, cat in enumerate(EXPENSE_CATEGORIES):
        row.append(_btn(cat, f"exp_cat_{i}"))
        if len(row) >= 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([_btn("Отмена", "cmd_cancel")])
    return _inline_keyboard(keyboard)


def build_yes_no_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Да", "yes"), _btn("Нет", "no")],
    ])


def build_expense_comment_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Пропустить", "exp_skip"), _btn("Отмена", "cmd_cancel")],
    ])


def build_income_comment_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Без комментария", "inc_skip"), _btn("Отмена", "cmd_cancel")],
    ])


def build_hours_quick_keyboard() -> dict:
    return _inline_keyboard([
        [
            _btn("4 ч", "hours_4"),
            _btn("6 ч", "hours_6"),
            _btn("8 ч", "hours_8"),
        ],
    ])


def build_main_menu_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Статус", "cmd_status"), _btn("Расход", "cmd_expense")],
        [_btn("Доход", "cmd_income"), _btn("Бюджет", "cmd_budget")],
        [_btn("Цели", "cmd_goals"), _btn("Долги", "cmd_debts")],
        [_btn("Подписки", "cmd_subscriptions"), _btn("Аналитика", "cmd_analytics")],
        [_btn("История", "cmd_history"), _btn("Шаблоны", "cmd_templates")],
        [_btn("Настройки", "cmd_settings"), _btn("Справка", "cmd_help")],
    ])


def build_cancel_keyboard() -> dict:
    return _inline_keyboard([[_btn("Отмена", "cmd_cancel")]])


def build_status_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Расход", "cmd_expense"), _btn("Доход", "cmd_income")],
    ])


def build_budget_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Задать план на месяц", "budget_set")],
        [_btn("Показать план и факт", "budget_status")],
        [_btn("Предложить план", "budget_suggest")],
        [_btn("Прогноз остатка", "budget_forecast")],
        [_btn("Назад", "cmd_help")],
    ])


def build_budget_categories_keyboard(month_year: str) -> dict:
    """For setting limits - use exp_cat_ indices."""
    row = []
    keyboard = []
    for i, cat in enumerate(EXPENSE_CATEGORIES):
        row.append(_btn(cat, f"budget_cat_{i}_{month_year}"))
        if len(row) >= 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([_btn("Назад", "cmd_budget")])
    return _inline_keyboard(keyboard)


def build_goals_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Список целей", "goals_list")],
        [_btn("Добавить цель", "goals_add")],
        [_btn("Пополнить цель", "goals_fund")],
        [_btn("Архив целей", "goals_archived")],
        [_btn("Назад", "cmd_help")],
    ])


def build_goal_select_keyboard(goals: list) -> dict:
    btns = [_btn(f"{g.name} ({int(g.current_amount)}/{int(g.target_amount)})", f"goal_fund_{g.id}") for g in goals[:5]]
    return _inline_keyboard([btns, [_btn("Отмена", "cmd_goals")]])


def build_subscriptions_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Список подписок", "subs_list")],
        [_btn("Добавить подписку", "subs_add")],
        [_btn("Просроченные", "subs_overdue")],
        [_btn("Назад", "cmd_help")],
    ])


def build_edit_last_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Изменить последний расход", "edit_last_expense")],
        [_btn("Удалить последний расход", "delete_last_expense")],
        [_btn("Отмена", "cmd_cancel")],
    ])


def build_debts_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Список долгов", "debts_list")],
        [_btn("Добавить долг", "debts_add")],
        [_btn("Назад", "cmd_help")],
    ])


def build_debt_direction_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Я должен", "debt_dir_owe"), _btn("Мне должны", "debt_dir_lent")],
        [_btn("Отмена", "cmd_cancel")],
    ])


def build_debt_detail_keyboard(debt_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Погасить частично", f"debt_pay_{debt_id}")],
        [_btn("История платежей", f"debt_history_{debt_id}")],
        [_btn("Назад", "cmd_debts")],
    ])


def build_debt_select_keyboard(debts: list) -> dict:
    btns = []
    for d in debts[:6]:
        label = f"{'←' if d.direction == 'owe' else '→'} {d.counterparty}: {int(d.remaining_amount)}"
        btns.append([_btn(label, f"debt_detail_{d.id}")])
    btns.append([_btn("Назад", "cmd_debts")])
    return _inline_keyboard(btns)


def build_analytics_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Отчёт за период", "analytics_period")],
        [_btn("Диаграмма расходов", "analytics_chart")],
        [_btn("Топ расходов", "analytics_top")],
        [_btn("Сравнение с прошлым", "analytics_compare")],
        [_btn("Среднее/день", "analytics_daily_avg")],
        [_btn("Назад", "cmd_help")],
    ])


def build_period_keyboard(prefix: str = "period") -> dict:
    return _inline_keyboard([
        [_btn("Неделя", f"{prefix}_week"), _btn("Месяц", f"{prefix}_month")],
        [_btn("Квартал", f"{prefix}_quarter"), _btn("Год", f"{prefix}_year")],
        [_btn("Назад", "cmd_analytics")],
    ])


def build_history_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Сегодня", "history_today"), _btn("Неделя", "history_week")],
        [_btn("Месяц", "history_month")],
        [_btn("Назад", "cmd_help")],
    ])


def build_templates_keyboard(templates: list) -> dict:
    btns = []
    for t in templates[:6]:
        btns.append([_btn(f"{t.name} ({int(t.amount)} руб.)", f"tpl_use_{t.id}")])
    btns.append([_btn("Добавить шаблон", "tpl_add")])
    btns.append([_btn("Назад", "cmd_help")])
    return _inline_keyboard(btns)


def build_date_choice_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Сегодня", "date_today"), _btn("Вчера", "date_yesterday")],
        [_btn("Другая дата", "date_custom")],
    ])


def build_recent_entries_keyboard(entries: list) -> dict:
    btns = []
    for e in entries[:5]:
        label = f"{e.date} {e.category}: {int(e.amount)}"
        btns.append([_btn(label, f"edit_entry_{e.id}")])
    btns.append([_btn("Отмена", "cmd_cancel")])
    return _inline_keyboard(btns)


def build_settings_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Тихие часы", "settings_quiet_hours")],
        [_btn("Уведомления", "settings_notifications")],
        [_btn("Порог крупного расхода", "settings_threshold")],
        [_btn("Экспорт данных", "cmd_export")],
        [_btn("Удалить все данные", "settings_delete_all")],
        [_btn("Назад", "cmd_help")],
    ])


def build_goal_type_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("✈️ Отпуск", "gtype_vacation"), _btn("💻 Техника", "gtype_tech")],
        [_btn("🛡️ Подушка", "gtype_cushion"), _btn("🛒 Покупка", "gtype_purchase")],
        [_btn("🎯 Другое", "gtype_other")],
    ])


def build_confirm_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Да, подтверждаю", "confirm_yes"), _btn("Отмена", "confirm_no")],
    ])
