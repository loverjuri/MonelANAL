"""Process incoming Telegram updates. Entry point from webhook."""
from collections import OrderedDict

from bot.handlers import handle_message, handle_callback_query, is_authorized_chat
from bot.telegram_api import send_message
from bot.keyboards import build_main_menu_keyboard
from db.repositories import get_session, log_info, log_error

# Simple dedup: keep last N update_ids to avoid processing retries
_SEEN_UPDATES: OrderedDict[int, None] = OrderedDict()
_MAX_SEEN = 500


def _is_update_processed(update_id: int) -> bool:
    if update_id in _SEEN_UPDATES:
        return True
    _SEEN_UPDATES[update_id] = None
    while len(_SEEN_UPDATES) > _MAX_SEEN:
        _SEEN_UPDATES.popitem(last=False)
    return False


def process_update(update: dict):
    """Route update to message or callback handler. Called from Flask webhook."""
    chat_id = None
    session = get_session()
    try:
        log_info(session, "Bot started")
        uid = update.get("update_id")
        if uid is not None and _is_update_processed(uid):
            return

        if "message" in update:
            msg = update["message"]
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text") or ("[document]" if msg.get("document") else "[media]")
            log_info(session, f"processUpdate: chatId={chat_id} {text[:50]}")
            if not is_authorized_chat(chat_id):
                send_message(
                    chat_id,
                    f"Ваш Chat ID ({chat_id}) не в списке разрешённых. Добавьте его в Config (CHAT_ID).",
                )
                return
            handle_message(chat_id, text or "", msg.get("message_id"), msg)

        elif "callback_query" in update:
            cq = update["callback_query"]
            chat_id = cq.get("message", {}).get("chat", {}).get("id")
            data = cq.get("data", "")
            msg_id = cq.get("message", {}).get("message_id")
            log_info(session, f"processUpdate callback: chatId={chat_id} cb:{data}")
            if not is_authorized_chat(chat_id):
                from bot.telegram_api import answer_callback_query
                answer_callback_query(cq.get("id", ""))
                send_message(chat_id, f"Ваш Chat ID ({chat_id}) не в списке разрешённых. Добавьте его в Config.")
                return
            handle_callback_query(chat_id, cq.get("id", ""), data, msg_id)
    except Exception as e:
        session.rollback()
        log_error(session, f"processUpdate: {e}")
        if chat_id:
            send_message(chat_id, "Произошла ошибка. Проверьте журнал и логи.")
    finally:
        session.close()
