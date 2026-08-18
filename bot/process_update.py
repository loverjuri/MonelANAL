"""Process incoming Telegram updates. Entry point from webhook."""
from collections import OrderedDict
from datetime import datetime, timedelta
from sqlalchemy import text

from bot.handlers import handle_message, handle_callback_query, is_authorized_chat
from bot.telegram_api import send_message
from db.repositories import get_session, log_error

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


def _claim_update(session, update_id: int) -> bool:
    """Persist update ids so webhook retries after restart are ignored."""
    try:
        result = session.execute(
            text("INSERT OR IGNORE INTO processed_updates (update_id, processed_at) "
                 "VALUES (:update_id, :processed_at)"),
            {"update_id": update_id, "processed_at": datetime.utcnow()},
        )
        session.commit()
        # Keep the table bounded; this runs only once per 100 updates.
        if update_id % 100 == 0:
            cutoff = datetime.utcnow() - timedelta(days=7)
            session.execute(text("DELETE FROM processed_updates WHERE processed_at < :cutoff"), {"cutoff": cutoff})
            session.commit()
        return result.rowcount == 0
    except Exception:
        session.rollback()
        # Migration may not have run yet; in-memory dedup remains a safe fallback.
        return _is_update_processed(update_id)


def _release_update(session, update_id: int | None):
    """Allow Telegram to retry an update if processing failed."""
    if update_id is None:
        return
    try:
        session.execute(text("DELETE FROM processed_updates WHERE update_id = :update_id"), {"update_id": update_id})
        session.commit()
    except Exception:
        session.rollback()


def process_update(update: dict):
    """Route update to message or callback handler. Called from Flask webhook."""
    chat_id = None
    uid = update.get("update_id")
    session = get_session()
    try:
        if uid is not None and _claim_update(session, uid):
            return

        if "message" in update:
            msg = update["message"]
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text") or ("[document]" if msg.get("document") else "[media]")
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
            if not is_authorized_chat(chat_id):
                from bot.telegram_api import answer_callback_query
                answer_callback_query(cq.get("id", ""))
                send_message(chat_id, f"Ваш Chat ID ({chat_id}) не в списке разрешённых. Добавьте его в Config.")
                return
            handle_callback_query(chat_id, cq.get("id", ""), data, msg_id)
    except Exception as e:
        session.rollback()
        _release_update(session, uid)
        log_error(session, f"processUpdate: {e}")
        if chat_id:
            send_message(chat_id, "Произошла ошибка. Проверьте журнал и логи.")
    finally:
        session.close()
