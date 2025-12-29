# SoulStart Devotion — Operator Runbook (V1 Stable)

## Deploy
1) Commit and push to GitHub:
- git add -A
- git commit -m "..."
- git push

2) Render deploy:
- Render auto-deploys from GitHub (watch the deploy logs)
- If deploy fails, open Render logs and read the first traceback

## Admin Access
- Admin login URL: /login
- Admin dashboard URL: /admin

## WhatsApp Send Workflow
1) Go to /admin
2) In “Send WhatsApp”:
   - Select Date
   - Select Mode (morning / night / both / verses)
   - (Optional) enable Dry run first to preview
3) Click Send
4) If not Dry run: the system opens WhatsApp Web with the message prefilled
5) Paste/Send in the correct WhatsApp chat

## Logs
- Admin WhatsApp logs (local): logs/admin_whatsapp_log.json
- Render logs: Render dashboard → your service → Logs tab

## Fallback Devotion (What it Means)
Fallback devotion shows when:
- A date is missing from the year JSON
- A mode block (morning/night) is missing
- The year file is not available
- JSON cannot be read (corrupted/unreadable)

Fallback is expected behavior (no crash).

### How to resolve missing devotions
1) Confirm the requested date exists in the source file:
- devotions/<YEAR>/devotions_<YEAR>.json

2) Confirm both mode blocks exist (morning/night if required)
3) Re-run normalization/export if needed
4) Re-deploy (git push → Render)

## If Deploy Fails (First Checks)
1) Render logs:
- Find the FIRST error traceback (ignore repeated noise below)
2) Common causes:
- Missing env vars
- Missing files in repo (static assets, devotions JSON)
- Template syntax errors (Jinja endblock, missing braces)
3) Fix locally, test, then push again
