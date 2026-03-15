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


def send_document(chat_id: int, document_path: str, caption: str = "") -> dict | None:
    """Send file as document."""
    if not BOT_TOKEN:
        return None
    url = f"{BASE}{BOT_TOKEN}/sendDocument"
    try:
        with open(document_path, "rb") as f:
            r = requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"document": f}, timeout=30)
        return r.json()
    except Exception:
        return None


def send_photo(chat_id: int, photo_path: str, caption: str = "") -> dict | None:
    """Send image as photo."""
    if not BOT_TOKEN:
        return None
    url = f"{BASE}{BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            r = requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"photo": f}, timeout=30)
        return r.json()
    except Exception:
        return None


def download_file(file_id: str, save_path: str) -> bool:
    """Download file by file_id from Telegram. Returns True on success."""
    if not BOT_TOKEN:
        return False
    try:
        r = requests.get(f"{BASE}{BOT_TOKEN}/getFile", params={"file_id": file_id}, timeout=10)
        data = r.json()
        if not data.get("ok"):
            return False
        path = data.get("result", {}).get("file_path")
        if not path:
            return False
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"
        r2 = requests.get(url, timeout=30)
        if r2.status_code != 200:
            return False
        with open(save_path, "wb") as f:
            f.write(r2.content)
        return True
    except Exception:
        return False
