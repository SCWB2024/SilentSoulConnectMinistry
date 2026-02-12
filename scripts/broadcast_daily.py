# scripts/broadcast_daily.py
import os
from soulstart.app import create_app  # adjust to your app factory if needed

def main():
    app = create_app()
    with app.app_context():
        from soulstart.services.broadcast import broadcast_today  # you create this
        result = broadcast_today()
        print(result)
        # exit code signals success/failure for Render logs
        raise SystemExit(0 if result.get("ok") else 1)

if __name__ == "__main__":
    main()
