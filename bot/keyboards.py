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
        [_btn("История учёта", "worklog_history"), _btn("Записать за дату", "worklog_add_past")],
    ])


def build_second_job_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Добавить заказ", "second_add")],
        [
            _btn("Нет доходов", "second_none"),
            _btn("Посмотреть статус", "second_status"),
        ],
        [_btn("Заказы за период", "orders_list"), _btn("Добавить за дату", "orders_add_past")],
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
        [_btn("Задать план на месяц", "budget_set"), _btn("Задать несколько", "budget_bulk")],
        [_btn("Показать план и факт", "budget_status")],
        [_btn("Предложить план", "budget_suggest")],
        [_btn("Прогноз остатка", "budget_forecast")],
        [_btn("Назад", "cmd_help")],
    ])


def build_worklog_period_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Сегодня", "worklog_period_today"), _btn("Неделя", "worklog_period_week")],
        [_btn("Месяц", "worklog_period_month")],
        [_btn("Записать за дату", "worklog_add_past")],
    ])


def build_worklog_list_keyboard(entries: list) -> dict:
    btns = [[_btn(f"{e.date} {e.hours_worked}ч {e.status}", f"worklog_edit_{e.id}")] for e in entries[:10]]
    btns.append([_btn("Назад", "main_full")])
    return _inline_keyboard(btns)


def build_orders_period_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Вчера", "orders_period_yesterday"), _btn("Неделя", "orders_period_week")],
        [_btn("Месяц", "orders_period_month")],
        [_btn("Добавить за дату", "orders_add_past")],
    ])


def build_orders_list_keyboard(orders: list) -> dict:
    btns = []
    for o in orders[:8]:
        btns.append([
            _btn(f"{o.date} {int(o.amount)}₽", f"order_edit_{o.order_id}"),
            _btn("✕", f"order_del_{o.order_id}"),
        ])
    btns.append([_btn("Назад", "second_status")])
    return _inline_keyboard(btns)


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
    btns = [_btn(f"{g.name} ({int(g.current_amount)}/{int(g.target_amount)})", f"goal_detail_{g.id}") for g in goals[:5]]
    return _inline_keyboard([btns, [_btn("Отмена", "cmd_goals")]])


def build_goal_detail_keyboard(goal_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Пополнить", f"goal_fund_{goal_id}"), _btn("Редактировать", f"goal_edit_{goal_id}")],
        [_btn("Перевести в другую цель", f"goal_transfer_{goal_id}")],
        [_btn("В архив", f"goal_archive_{goal_id}")],
        [_btn("Назад", "cmd_goals")],
    ])


def build_goal_edit_field_keyboard(goal_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Название", f"goal_edit_name_{goal_id}"), _btn("Цель (сумма)", f"goal_edit_target_{goal_id}")],
        [_btn("Текущее", f"goal_edit_current_{goal_id}"), _btn("Срок", f"goal_edit_deadline_{goal_id}")],
        [_btn("Приоритет", f"goal_edit_priority_{goal_id}"), _btn("Тип", f"goal_edit_type_{goal_id}")],
        [_btn("Авто %", f"goal_edit_autopct_{goal_id}"), _btn("Авто сумма", f"goal_edit_autoamt_{goal_id}")],
        [_btn("Назад", "cmd_back"), _btn("Готово", "cmd_cancel")],
    ])


def build_goal_transfer_target_keyboard(goals: list, from_goal_id: str) -> dict:
    btns = []
    for g in goals:
        if g.id != from_goal_id:
            btns.append([_btn(f"{g.name} ({int(g.current_amount)}/{int(g.target_amount)})", f"goal_transfer_to_{g.id}_{from_goal_id}")])
    btns.append([_btn("Отмена", "cmd_cancel")])
    return _inline_keyboard(btns)


def build_subscriptions_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Список подписок", "subs_list")],
        [_btn("Добавить подписку", "subs_add")],
        [_btn("Просроченные", "subs_overdue"), _btn("Приостановленные", "subs_paused")],
        [_btn("Назад", "cmd_help")],
    ])


def build_subs_select_keyboard(subs: list) -> dict:
    btns = [_btn(f"{s.name} ({int(s.amount)}₽)", f"subs_detail_{s.id}") for s in subs[:8]]
    return _inline_keyboard([btns, [_btn("Назад", "cmd_subscriptions")]])


def build_subs_detail_keyboard(sub_id: str, is_active: bool) -> dict:
    btns = [
        [_btn("Редактировать", f"subs_edit_{sub_id}")],
    ]
    if is_active:
        btns.append([_btn("Пауза", f"subs_pause_{sub_id}")])
    else:
        btns.append([_btn("Возобновить", f"subs_resume_{sub_id}")])
    btns.append([_btn("Удалить", f"subs_delete_{sub_id}")])
    btns.append([_btn("Назад", "subs_list")])
    return _inline_keyboard(btns)


def build_subs_edit_field_keyboard(sub_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Название", f"subs_edit_name_{sub_id}"), _btn("Сумма", f"subs_edit_amount_{sub_id}")],
        [_btn("Цикл", f"subs_edit_cycle_{sub_id}"), _btn("След. дата", f"subs_edit_next_{sub_id}")],
        [_btn("Категория", f"subs_edit_cat_{sub_id}"), _btn("Напомин. дней", f"subs_edit_remind_{sub_id}")],
        [_btn("Авто расход", f"subs_edit_auto_{sub_id}"), _btn("Группа", f"subs_edit_group_{sub_id}")],
        [_btn("Назад", "cmd_back"), _btn("Готово", "cmd_cancel")],
    ])


def build_subs_cycle_keyboard(sub_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Ежемесячно", f"subs_cycle_monthly_{sub_id}"), _btn("Еженедельно", f"subs_cycle_weekly_{sub_id}")],
        [_btn("Ежегодно", f"subs_cycle_yearly_{sub_id}")],
    ])


def build_subs_group_keyboard(sub_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Стриминг", f"subs_group_streaming_{sub_id}"), _btn("Облако", f"subs_group_cloud_{sub_id}")],
        [_btn("Банк", f"subs_group_bank_{sub_id}"), _btn("Другое", f"subs_group_other_{sub_id}")],
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


def build_debt_kind_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Кредит", "debt_kind_credit"), _btn("Рассрочка", "debt_kind_installment")],
        [_btn("Кредитная карта", "debt_kind_card"), _btn("Овердрафт", "debt_kind_overdraft")],
        [_btn("Отмена", "cmd_cancel")],
    ])


def build_debt_payment_mode_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Рассчитать платёж", "debt_pmode_calc"), _btn("Ввести сумму из банка", "debt_pmode_enter")],
        [_btn("Отмена", "cmd_cancel")],
    ])


def build_debt_payment_type_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Аннуитетный", "debt_ptype_annuity"), _btn("Дифференцированный", "debt_ptype_fixed")],
        [_btn("Отмена", "cmd_cancel")],
    ])


def build_debt_cycle_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Ежемесячно", "debt_cycle_monthly"), _btn("Раз в 2 недели", "debt_cycle_biweekly")],
        [_btn("Отмена", "cmd_cancel")],
    ])


def build_debt_confirm_payment_keyboard(amount: float) -> dict:
    return _inline_keyboard([
        [_btn(f"Подтвердить ({int(amount)} руб.)", "debt_confirm_yes"), _btn("Ввести свою сумму", "debt_confirm_custom")],
        [_btn("Отмена", "cmd_cancel")],
    ])


def build_debt_detail_keyboard(debt_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Погасить частично", f"debt_pay_{debt_id}"), _btn("Редактировать", f"debt_edit_{debt_id}")],
        [_btn("История платежей", f"debt_history_{debt_id}")],
        [_btn("Назад", "cmd_debts")],
    ])


def build_debt_edit_field_keyboard(debt_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Контрагент", f"debt_edit_counterparty_{debt_id}"), _btn("Сумма", f"debt_edit_amount_{debt_id}")],
        [_btn("Остаток", f"debt_edit_remaining_{debt_id}"), _btn("Ставка %", f"debt_edit_rate_{debt_id}")],
        [_btn("Платёж", f"debt_edit_payment_{debt_id}"), _btn("Цикл", f"debt_edit_cycle_{debt_id}")],
        [_btn("Дата след.", f"debt_edit_next_{debt_id}"), _btn("Срок", f"debt_edit_due_{debt_id}")],
        [_btn("Тип долга", f"debt_edit_kind_{debt_id}")],
        [_btn("Назад", "cmd_back"), _btn("Готово", "cmd_cancel")],
    ])


def build_debt_cycle_edit_keyboard(debt_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Ежемесячно", f"debt_cycle_val_monthly_{debt_id}"), _btn("Раз в 2 нед.", f"debt_cycle_val_biweekly_{debt_id}")],
    ])


def build_debt_kind_edit_keyboard(debt_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Кредит", f"debt_kind_val_credit_{debt_id}"), _btn("Рассрочка", f"debt_kind_val_installment_{debt_id}")],
        [_btn("Кредитная карта", f"debt_kind_val_card_{debt_id}"), _btn("Овердрафт", f"debt_kind_val_overdraft_{debt_id}")],
    ])


def build_debt_history_keyboard(debt_id: str, payments: list) -> dict:
    btns = []
    for p in payments[:8]:
        btns.append([
            _btn(f"{p.date} {int(p.amount)}₽", f"debt_pay_edit_{p.id}"),
            _btn("✕", f"debt_pay_del_{p.id}"),
        ])
    btns.append([_btn("Добавить платёж", f"debt_pay_add_{debt_id}")])
    btns.append([_btn("Назад", f"debt_detail_{debt_id}")])
    return _inline_keyboard(btns)


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
        btns.append([
            _btn(f"{t.name} ({int(t.amount)}₽)", f"tpl_use_{t.id}"),
            _btn("✎", f"tpl_edit_{t.id}"),
        ])
    btns.append([_btn("Добавить шаблон", "tpl_add")])
    btns.append([_btn("Назад", "cmd_help")])
    return _inline_keyboard(btns)


def build_tpl_edit_keyboard(tpl_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Название", f"tpl_edit_name_{tpl_id}"), _btn("Сумма", f"tpl_edit_amount_{tpl_id}")],
        [_btn("Категория", f"tpl_edit_cat_{tpl_id}")],
        [_btn("Удалить", f"tpl_del_{tpl_id}"), _btn("Назад", "cmd_back"), _btn("Готово", "cmd_templates")],
    ])


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


def build_finance_edit_field_keyboard(finance_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Дата", f"edit_fin_field_date_{finance_id}"), _btn("Сумма", f"edit_fin_field_amount_{finance_id}")],
        [_btn("Тип", f"edit_fin_field_type_{finance_id}"), _btn("Категория", f"edit_fin_field_cat_{finance_id}")],
        [_btn("Комментарий", f"edit_fin_field_comment_{finance_id}"), _btn("Искл. из бюджета", f"edit_fin_field_excl_{finance_id}")],
        [_btn("Удалить", f"edit_fin_soft_del_{finance_id}")],
        [_btn("Назад", "cmd_back"), _btn("Готово", "cmd_cancel")],
    ])


def build_finance_type_keyboard(finance_id: str) -> dict:
    return _inline_keyboard([
        [_btn("Расход", f"edit_fin_type_Expense_{finance_id}"), _btn("Доход", f"edit_fin_type_IncomeSecond_{finance_id}")],
        [_btn("Корректировка", f"edit_fin_type_Correction_{finance_id}")],
    ])


CONFIG_PARAMS = [
    ("FixedSalary", "Оклад"),
    ("PayDay1", "День зарплаты 1"),
    ("PayDay2", "День зарплаты 2"),
    ("ChatID", "Chat ID"),
    ("LargeExpenseThreshold", "Порог крупного расхода"),
    ("QuietHoursStart", "Тихие часы: начало"),
    ("QuietHoursEnd", "Тихие часы: конец"),
    ("WorkHoursNorm", "Норма часов"),
]


def build_settings_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Тихие часы", "settings_quiet_hours")],
        [_btn("Уведомления", "settings_notifications")],
        [_btn("Порог крупного расхода", "settings_threshold")],
        [_btn("Конфигурация", "settings_config")],
        [_btn("Редактирование", "edit_menu")],
        [_btn("Теги", "settings_tags"), _btn("Достижения", "settings_achievements")],
        [_btn("Расчёты ЗП", "settings_calculations")],
        [_btn("Импорт Excel", "import_excel")],
        [_btn("Экспорт данных", "cmd_export")],
        [_btn("Удалить все данные", "settings_delete_all")],
        [_btn("Назад", "cmd_help")],
    ])


def build_edit_menu_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Финансы", "cmd_history"), _btn("Долги", "cmd_debts")],
        [_btn("Цели", "cmd_goals"), _btn("Подписки", "cmd_subscriptions")],
        [_btn("Бюджет", "cmd_budget"), _btn("WorkLog", "worklog_history")],
        [_btn("Заказы", "orders_list"), _btn("Шаблоны", "cmd_templates")],
        [_btn("Массовые операции", "finance_mass")],
        [_btn("Назад", "cmd_settings")],
    ])


def build_mass_period_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Неделя", "mass_period_week"), _btn("Месяц", "mass_period_month")],
    ])


def build_mass_category_keyboard() -> dict:
    row, btns = [], []
    for i, cat in enumerate(EXPENSE_CATEGORIES[:8]):
        row.append(_btn(cat, f"mass_cat_{i}"))
        if len(row) >= 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([_btn("Все категории", "mass_cat_all")])
    btns.append([_btn("Отмена", "cmd_cancel")])
    return _inline_keyboard(btns)


def build_mass_action_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Удалить выбранное", "mass_action_delete")],
        [_btn("Исключить из бюджета", "mass_action_exclude")],
        [_btn("Отмена", "cmd_cancel")],
    ])


def build_tags_keyboard(tags: list) -> dict:
    btns = [[_btn(f"{t.name}", f"tag_edit_{t.id}"), _btn("✕", f"tag_del_{t.id}")] for t in tags[:10]]
    btns.append([_btn("Добавить тег", "tag_add")])
    btns.append([_btn("Назад", "cmd_settings")])
    return _inline_keyboard(btns)


def build_achievements_keyboard(achievements: list) -> dict:
    btns = [[_btn(f"🏆 {a.name}", f"ach_reset_{a.id}")] for a in achievements[:10]]
    btns.append([_btn("Назад", "cmd_settings")])
    return _inline_keyboard(btns)


def build_calculations_keyboard(calcs: list) -> dict:
    btns = [[_btn(f"{c.period_start}–{c.period_end}: {int(c.received_salary or 0)}₽", f"calc_edit_{c.id}")] for c in calcs[:8]]
    btns.append([_btn("Назад", "cmd_settings")])
    return _inline_keyboard(btns)


def build_config_params_keyboard() -> dict:
    btns = [[_btn(label, f"config_edit_{param}")] for param, label in CONFIG_PARAMS]
    btns.append([_btn("Назад", "cmd_settings")])
    return _inline_keyboard(btns)


def build_goal_type_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("✈️ Отпуск", "gtype_vacation"), _btn("💻 Техника", "gtype_tech")],
        [_btn("🛡️ Подушка", "gtype_cushion"), _btn("🛒 Покупка", "gtype_purchase")],
        [_btn("🎯 Другое", "gtype_other")],
    ])


def build_goal_type_keyboard_for_edit(goal_id: str) -> dict:
    return _inline_keyboard([
        [_btn("✈️ Отпуск", f"gtype_edit_vacation_{goal_id}"), _btn("💻 Техника", f"gtype_edit_tech_{goal_id}")],
        [_btn("🛡️ Подушка", f"gtype_edit_cushion_{goal_id}"), _btn("🛒 Покупка", f"gtype_edit_purchase_{goal_id}")],
        [_btn("🎯 Другое", f"gtype_edit_other_{goal_id}")],
    ])


def build_confirm_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Да, подтверждаю", "confirm_yes"), _btn("Отмена", "confirm_no")],
    ])


def build_import_exclude_budget_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Да, исключить", "import_exclude_yes"), _btn("Нет", "import_exclude_no")],
        [_btn("Отмена", "cmd_cancel")],
    ])


def build_import_rows_keyboard(rows: list, start_idx: int, pending: set) -> dict:
    """Rows: full list, start_idx: page offset, pending: set of indices not yet added/skipped."""
    btns = []
    pending_list = sorted(pending)
    if not pending_list:
        return _inline_keyboard([[_btn("Готово", "import_done")]])
    page = pending_list[start_idx : start_idx + 5]
    for idx in page:
        r = rows[idx]
        amt = int(r.get("amount", 0))
        lbl = f"{r.get('date','')} {amt}"
        btns.append([
            _btn(f"+ {lbl}", f"import_add_{idx}"),
            _btn(f"- {lbl}", f"import_skip_{idx}"),
        ])
    nav = []
    if start_idx > 0:
        nav.append(_btn("← Назад", f"import_page_{start_idx - 5}"))
    if start_idx + 5 < len(pending_list):
        nav.append(_btn("Вперёд →", f"import_page_{start_idx + 5}"))
    if nav:
        btns.append(nav)
    btns.append([_btn("Готово", "import_done")])
    return _inline_keyboard(btns)
