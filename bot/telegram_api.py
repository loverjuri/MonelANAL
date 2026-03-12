"""Telegram Bot API: send messages, answer callbacks. Sync HTTP via requests."""
import json
import requests
from typing import Any

from config import BOT_TOKEN

BASE = "https://api.telegram.org/bot"


def _api(method: str, payload: dict) -> dict | None:
    if not BOT_TOKEN:
        return None
    url = f"{BASE}{BOT_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception:
        return None


def send_message(
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
) -> dict | None:
    body: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        body["reply_markup"] = json.dumps(reply_markup)
    return _api("sendMessage", body)


def answer_callback_query(callback_query_id: str) -> dict | None:
    return _api("answerCallbackQuery", {"callback_query_id": callback_query_id})


def edit_message_text(
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: dict | None = None,
) -> dict | None:
    body: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        body["reply_markup"] = json.dumps(reply_markup)
    return _api("editMessageText", body)
