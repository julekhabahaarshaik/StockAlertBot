"""
config.py
---------
All settings live here. Secrets (Telegram token, email password, etc.)
are read from environment variables — NEVER hardcode them in this file.

Locally, you can create a `.env` file (see .env.example) and it will be
loaded automatically. On GitHub Actions, these come from repo Secrets.
"""

import os
from pathlib import Path

# Try to load a local .env file for testing on your own PC.
# On GitHub Actions this simply does nothing (no .env file exists there).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent

# ---------- Telegram ----------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------- Email backup (optional) ----------
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "")          # your Gmail address
EMAIL_PASS = os.getenv("EMAIL_PASS", "")          # Gmail App Password (not your normal password)
EMAIL_TO = os.getenv("EMAIL_TO", EMAIL_USER)       # who receives the backup mail

# Only send email backup for alerts at/above this severity (1-5 stars)
EMAIL_MIN_SEVERITY = int(os.getenv("EMAIL_MIN_SEVERITY", "4"))

# ---------- Files ----------
COMPANIES_FILE = BASE_DIR / "companies.json"
DB_FILE = BASE_DIR / "database.db"
LOG_FILE = BASE_DIR / "bot.log"

# ---------- Behaviour ----------
# How many days back to look on the very first run (so you don't get
# flooded with months of old announcements the first time it executes).
LOOKBACK_DAYS_FIRST_RUN = int(os.getenv("LOOKBACK_DAYS_FIRST_RUN", "2"))

# IST is UTC+5:30. Used to decide when to send the daily summary.
IST_OFFSET_HOURS = 5.5
DAILY_SUMMARY_HOUR_IST = 18  # 6 PM
