#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
LOCALE = os.getenv("BOT_LOCALE", "uz")
POLL_TIMEOUT = int(os.getenv("BOT_POLL_TIMEOUT", "30"))

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TOKEN}"
chat_state: dict[int, dict[str, str]] = {}


def _http_json(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _telegram(method: str, payload: dict | None = None) -> dict:
    url = f"{TELEGRAM_API_BASE}/{method}"
    return _http_json("POST", url, payload or {})


def send_message(chat_id: int, text: str) -> None:
    _telegram("sendMessage", {"chat_id": chat_id, "text": text})


def call_backend_start_session(telegram_user_id: int, bxm_code: str) -> tuple[bool, str]:
    payload = {
        "telegram_user_id": telegram_user_id,
        "locale": LOCALE,
        "fio_input": "",
        "bxm_code": bxm_code,
    }
    url = f"{BACKEND_BASE_URL}/v1/bot/session/start"
    try:
        response = _http_json("POST", url, payload)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(raw)
            return False, parsed.get("message_text", "Xatolik yuz berdi")
        except json.JSONDecodeError:
            return False, f"Backend HTTP error: {exc.code}"
    except urllib.error.URLError:
        return False, "Backend bilan aloqa yo'q. API serverni tekshiring."

    message_text = response.get("message_text", "BXM tasdiqlandi")
    return True, message_text


def handle_text(chat_id: int, user_id: int, text: str) -> None:
    text = text.strip()

    if text in {"/start", "start"}:
        chat_state[chat_id] = {"step": "await_bxm"}
        send_message(
            chat_id,
            "Assalomu alaykum! BXM kodini yuboring (masalan: 12345).",
        )
        return

    state = chat_state.get(chat_id, {})
    if state.get("step") != "await_bxm":
        send_message(chat_id, "Botni boshlash uchun /start ni bosing.")
        return

    if not text.isdigit() or len(text) != 5:
        send_message(chat_id, "BXM kodi 5 xonali son bo'lishi kerak. Qaytadan kiriting.")
        return

    ok, msg = call_backend_start_session(user_id, text)
    send_message(chat_id, msg)
    if ok:
        chat_state[chat_id] = {"step": "ready", "bxm_code": text}


def run_polling() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    offset = 0
    print("Telegram bot runner started")
    print(f"Backend: {BACKEND_BASE_URL}")
    while True:
        try:
            updates = _telegram("getUpdates", {"offset": offset, "timeout": POLL_TIMEOUT})
        except urllib.error.URLError:
            time.sleep(3)
            continue

        for item in updates.get("result", []):
            offset = item["update_id"] + 1
            message = item.get("message") or {}
            chat = message.get("chat") or {}
            user = message.get("from") or {}
            text = message.get("text", "")
            chat_id = chat.get("id")
            user_id = user.get("id")
            if not chat_id or not user_id or not text:
                continue
            handle_text(chat_id, user_id, text)


if __name__ == "__main__":
    run_polling()
