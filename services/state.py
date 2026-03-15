"""FSM state: get_state, set_state, clear_state via db."""
from datetime import datetime, timedelta
from db.repositories import get_session, get_state as _db_get_state, set_state as _db_set_state, clear_state as _db_clear_state

FSM_TIMEOUT_MINUTES = 15


def get_state(chat_id) -> dict | None:
    session = get_session()
    try:
        state = _db_get_state(session, chat_id)
        if state:
            updated = state.get("updatedAt")
            if updated:
                try:
                    age = datetime.utcnow() - updated
                    if age > timedelta(minutes=FSM_TIMEOUT_MINUTES):
                        _db_clear_state(session, chat_id)
                        return None
                except (TypeError, ValueError):
                    pass
        return state
    finally:
        session.close()


def set_state(chat_id, scenario: str, step: str, payload: dict):
    session = get_session()
    try:
        _db_set_state(session, chat_id, scenario, step, payload)
    finally:
        session.close()


def clear_state(chat_id):
    session = get_session()
    try:
        _db_clear_state(session, chat_id)
    finally:
        session.close()
