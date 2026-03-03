import os
from datetime import date

LIVE_DEVOTION_URL = os.getenv("LIVE_DEVOTION_URL", "")
JOIN_CHAT_URL = os.getenv("JOIN_CHAT_URL", "")

def build_messages(devotion_text: str):
    wa_chat_msg = (
        "🌅 SoulStart Sunrise\n"
        "Today’s devotion is ready.\n"
        f"Join our WhatsApp chat to receive it daily:\n{JOIN_CHAT_URL}\n"
    )

    public_msg = (
        "🌅 SoulStart Sunrise\n"
        f"{devotion_text}\n\n"
        f"Read today’s devotion here: {LIVE_DEVOTION_URL}\n"
    )

    return wa_chat_msg, public_msg

def broadcast_today():
    # 1) load today devotion (use YOUR existing loader)
    devotion_text = load_today_devotion_text()  # <-- connect to your current function

    wa_chat_msg, public_msg = build_messages(devotion_text)

    results = {}

    # 2) send using YOUR existing API senders
    results["whatsapp_chat"] = send_whatsapp_chat(wa_chat_msg)     # join link only
    results["whatsapp_status"] = send_whatsapp_status(public_msg)  # live link
    results["whatsapp_channel"] = send_whatsapp_channel(public_msg)
    results["facebook"] = post_facebook(public_msg)
    results["linkedin"] = post_linkedin(public_msg)

    ok = all(v.get("ok") for v in results.values())

    return {"ok": ok, "date": str(date.today()), "results": results}
