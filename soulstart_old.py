import os
import json
from datetime import datetime

# Get the folder where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# File paths
DEVOTIONS_FILE = os.path.join(BASE_DIR, "devotions.json")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_FOLDER, "devotion_log.txt")

# ✅ Ensure logs folder exists
os.makedirs(LOG_FOLDER, exist_ok=True)

# Branding banner
def show_banner():
    print("=" * 60)
    print("   ____             _ _     _____ _             _   ")
    print("  / ___| ___   ___ | | |   | ____| |_   _  __ _| |_ ")
    print(" | |  _ / _ \\ / _ \\| | |   |  _| | | | | |/ _` | __|")
    print(" | |_| | (_) | (_) | | |   | |___| | |_| | (_| | |_ ")
    print("  \\____|\\___/ \\___/|_|_|   |_____|_|\\__,_|\\__,_|\\__|")
    print("=" * 60)
    print("        🌅 SoulStart Console - Strength for the Day, Peace for the Night")
    print("=" * 60)

# Load devotions from JSON file
def load_devotions():
    if not os.path.exists(DEVOTIONS_FILE):
        print(f"⚠️ Devotions file not found: {DEVOTIONS_FILE}")
        return []
    with open(DEVOTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# Get today's devotion
def get_today_devotion(devotions):
    if not devotions:
        return None
    day_number = datetime.now().timetuple().tm_yday
    return devotions[day_number % len(devotions)]

# Display devotion with Blessing
def display_devotion(mode, devotions):
    devotion = get_today_devotion(devotions)
    if not devotion:
        print("⚠️ No devotions available.")
        return
    
    print("\n" + "=" * 60)
    if mode == "morning":
        print(f"🌅 SoulStart Morning Devotion - {datetime.now().strftime('%A, %B %d, %Y')}")
        print("=" * 60)
        print(f"Theme: {devotion['theme']}")
        print(f"📖 Scripture: {devotion['scripture']}")
        print(f"💡 Reflection: {devotion['reflection']}")
        print(f"📜 Declaration: {devotion['declaration']}")
        print(f"💎 Blessing: {devotion['blessing']}")
        print(f"🙏 Morning Prayer: {devotion['morning_prayer']}")
    elif mode == "night":
        print(f"🌙 SoulStart Night Prayer - {datetime.now().strftime('%A, %B %d, %Y')}")
        print("=" * 60)
        print(f"Theme: {devotion['theme']}")
        print(f"📖 Scripture: {devotion['scripture']}")
        print(f"📜 Declaration: {devotion['declaration']}")
        print(f"💎 Blessing: {devotion['blessing']}")
        print(f"🙏 Night Prayer: {devotion['night_prayer']}")
    print("=" * 60 + "\n")
    
    log_devotion(mode, devotion['theme'])

# Log devotion read
def log_devotion(mode, theme):
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {mode.title()} devotion viewed - Theme: {theme}\n")
    print(f"✅ Devotion saved to: {LOG_FILE}")

# Main program
if __name__ == "__main__":
    show_banner()
    devotions = load_devotions()
    choice = input("Select mode (morning/night): ").strip().lower()
    if choice in ["morning", "night"]:
        display_devotion(choice, devotions)
    else:
        print("⚠️ Invalid choice. Please type 'morning' or 'night'.")
