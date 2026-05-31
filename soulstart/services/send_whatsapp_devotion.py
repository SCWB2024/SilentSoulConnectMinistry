# -*- coding: utf-8 -*-

import sys
import time
import webbrowser
import platform
import pyautogui
import pyperclip
from datetime import datetime
from pathlib import Path

from soulstart.services.build_whatsapp_message import build_whatsapp_message

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_MODE = "morning"
DEFAULT_CHAT = "Silent SoulConnect Ministry"


def countdown(label, seconds):
    for i in range(seconds, 0, -1):
        print(f"{label}: {i:>2}s", end="\r", flush=True)
        time.sleep(1)
    print(" " * 60, end="\r", flush=True)


def run_automation(message, chat_name=None, auto_send=False):
    print("Opening WhatsApp Web...")
    webbrowser.open("https://web.whatsapp.com/")
    time.sleep(6)

    print("\nSTEP 1: Make sure WhatsApp Web is open.")
    print("STEP 2: Open the correct chat manually, or use chat search later.")
    print("STEP 3: Click inside the message box.")
    input("👉 When cursor is blinking in the WhatsApp message box, press ENTER here...")

    countdown("Pasting in", 5)

    pyperclip.copy(message)

    meta_key = "command" if platform.system() == "Darwin" else "ctrl"
    pyautogui.hotkey(meta_key, "v")
    time.sleep(1)

    if auto_send:
        pyautogui.press("enter")
        print("✅ Message pasted and sent.")
    else:
        print("✅ Message pasted. Press Enter in WhatsApp to send.")


def main():
    print("--- SSCM Devotion Sender Started ---")

    target_date = datetime.now().strftime("%Y-%m-%d")
    mode = DEFAULT_MODE

    message = build_whatsapp_message(target_date, mode)

    if not message or "No devotion found" in message:
        print(message)
        return

    print("\n--- Message Preview ---\n")
    print(message)
    print("\n-----------------------\n")

    run_automation(message, auto_send=False)


if __name__ == "__main__":
    main()