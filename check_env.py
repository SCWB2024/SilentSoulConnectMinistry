from pathlib import Path
import re

ENV_PATH = Path(__file__).parent / ".env"
BAD = False

# A simple, safe .env rule: KEY=VALUE (KEY is letters/numbers/underscore, cannot start with a number)
key_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

print(f"Checking: {ENV_PATH}\n")

with ENV_PATH.open("r", encoding="utf-8") as f:
    for i, raw in enumerate(f, start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()

        # skip blanks and comments
        if not stripped or stripped.startswith("#"):
            continue

        # must contain '=' exactly once (left & right parts non-empty)
        if "=" not in stripped:
            print(f"Line {i}: ❌ missing '='  →  {line}")
            BAD = True
            continue

        # split only on the first '=' so values may contain '='
        key, value = stripped.split("=", 1)

        if not key_re.match(key.strip()):
            print(f"Line {i}: ❌ invalid KEY '{key.strip()}'  →  {line}")
            BAD = True
            continue

        # common mistakes
        # 1) accidental colon instead of equals (caught above, but hint)
        if ":" in key:
            print(f"Line {i}: ❌ looks like you used ':' instead of '='  →  {line}")
            BAD = True

        # 2) smart quotes
        if "“" in value or "”" in value or "‘" in value or "’" in value:
            print(f"Line {i}: ⚠ smart quotes detected; replace with normal quotes  →  {line}")
            BAD = True

        # 3) unbalanced quotes
        v = value.strip()
        if (v.startswith('"') and not v.endswith('"')) or (v.startswith("'") and not v.endswith("'")):
            print(f"Line {i}: ❌ unbalanced quotes  →  {line}")
            BAD = True

        # 4) inline comments without a separator
        if " #" in value:
            # okay (space + #) is usually fine; python-dotenv supports it if quoted properly
            pass

if not BAD:
    print("✅ .env looks syntactically OK (basic checks).")
else:
    print("\nFix the lines above and re-run.")
