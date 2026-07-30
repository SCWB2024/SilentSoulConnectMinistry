import os
import requests
from datetime import date

from app import load_devotion_for, build_whatsapp_message

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
WHATSAPP_TO = os.getenv("WHATSAPP_TO")


def send_whatsapp_text(message: str):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID or not WHATSAPP_TO:
        return {"ok": False, "error": "Missing WhatsApp environment variables"}

    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": WHATSAPP_TO,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": message,
        },
    }

    r = requests.post(url, headers=headers, json=payload, timeout=30)

    if r.ok:
        return {"ok": True, "status": r.status_code, "response": r.json()}

    return {
        "ok": False,
        "status": r.status_code,
        "error": r.text,
    }


def broadcast_today(mode="morning"):
    today = date.today()

    entry = load_devotion_for(today, mode)

    if not entry:
        return {"ok": False, "error": f"No {mode} devotion found for {today}"}

    message = build_whatsapp_message(today.isoformat(), mode)

    return send_whatsapp_text(message)