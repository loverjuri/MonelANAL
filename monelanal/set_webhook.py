#!/usr/bin/env python3
"""Set Telegram webhook. Run after deploy. Requires BOT_TOKEN and WEBHOOK_URL env."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").strip()


def set_webhook():
    if not BOT_TOKEN:
        print("BOT_TOKEN not set")
        return 1
    if not WEBHOOK_URL:
        print("WEBHOOK_URL not set. Example: https://USERNAME.pythonanywhere.com/webhook")
        return 1
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    r = requests.post(url, json={"url": WEBHOOK_URL}, timeout=10)
    print(r.json())
    return 0


def delete_webhook():
    if not BOT_TOKEN:
        print("BOT_TOKEN not set")
        return 1
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    r = requests.post(url, timeout=10)
    print(r.json())
    return 0


def check_webhook():
    if not BOT_TOKEN:
        print("BOT_TOKEN not set")
        return 1
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    r = requests.get(url, timeout=10)
    data = r.json()
    if data.get("ok") and data.get("result"):
        wh = data["result"].get("url", "(не установлен)")
        print(f"Webhook: {wh}")
    else:
        print(data)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "set"
    if cmd == "delete":
        sys.exit(delete_webhook())
    if cmd == "check":
        sys.exit(check_webhook())
    sys.exit(set_webhook())
