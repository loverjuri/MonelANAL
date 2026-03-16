"""Inline keyboards for Telegram bot (slim: notifications + quick actions only)."""

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
    return {"inline_keyboard": buttons}


def _btn(text: str, callback_data: str) -> dict:
    return {"text": text, "callback_data": callback_data}


def _web_app_btn(text: str, url: str) -> dict:
    return {"text": text, "web_app": {"url": url}}


def _get_web_url() -> str:
    try:
        from config import get_web_app_url
        return get_web_app_url() or ""
    except Exception:
        return ""


def build_main_menu_keyboard() -> dict:
    rows = [
        [_btn("Статус", "cmd_status"), _btn("Расход", "cmd_expense")],
    ]
    url = _get_web_url()
    if url:
        rows.append([_web_app_btn("Открыть приложение", url)])
    return _inline_keyboard(rows)


def build_cancel_keyboard() -> dict:
    return _inline_keyboard([[_btn("Отмена", "cmd_cancel")]])


def build_status_keyboard() -> dict:
    rows = [
        [_btn("Расход", "cmd_expense")],
    ]
    url = _get_web_url()
    if url:
        rows.append([_web_app_btn("Открыть приложение", url)])
    return _inline_keyboard(rows)


# --- Work prompts ---
def build_main_work_keyboard() -> dict:
    rows = [
        [_btn("Полный (8ч)", "main_full"), _btn("Частично", "main_partial")],
        [_btn("Не работал", "main_none"), _btn("Выходной (работал)", "main_weekend")],
        [_btn("Больничный", "main_sick")],
    ]
    url = _get_web_url()
    if url:
        base = url.rstrip("/").rsplit("/", 1)[0]
        rows.append([_web_app_btn("Подробнее в приложении", base + "/worklog")])
    return _inline_keyboard(rows)


def build_hours_quick_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("4 ч", "hours_4"), _btn("6 ч", "hours_6"), _btn("8 ч", "hours_8")],
    ])


# --- Second job prompts ---
def build_second_job_keyboard() -> dict:
    rows = [
        [_btn("Добавить заказ", "second_add")],
        [_btn("Нет доходов", "second_none"), _btn("Статус", "second_status")],
    ]
    url = _get_web_url()
    if url:
        base = url.rstrip("/").rsplit("/", 1)[0]
        rows.append([_web_app_btn("Заказы в приложении", base + "/orders")])
    return _inline_keyboard(rows)


def build_yes_no_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Да", "yes"), _btn("Нет", "no")],
    ])


# --- Quick expense ---
def build_expense_categories_keyboard() -> dict:
    row, keyboard = [], []
    for i, cat in enumerate(EXPENSE_CATEGORIES):
        row.append(_btn(cat, f"exp_cat_{i}"))
        if len(row) >= 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([_btn("Отмена", "cmd_cancel")])
    return _inline_keyboard(keyboard)


def build_expense_comment_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Пропустить", "exp_skip"), _btn("Отмена", "cmd_cancel")],
    ])


# --- Payday ---
def build_confirm_keyboard() -> dict:
    return _inline_keyboard([
        [_btn("Да, подтверждаю", "confirm_yes"), _btn("Отмена", "confirm_no")],
    ])
