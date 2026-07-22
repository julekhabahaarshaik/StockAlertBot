"""
utils.py
--------
Helper functions used by main.py:
  - SQLite storage so we never send the same announcement twice
  - Keyword-based classifier that guesses category + a 1-5 star "impact" score
  - Telegram and email senders
"""

import logging
import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

import requests

import config

logging.basicConfig(
    filename=str(config.LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("stockbot")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
log.addHandler(console)


# ---------------------------------------------------------------------------
# Database (duplicate protection + history for the daily summary)
# ---------------------------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(str(config.DB_FILE))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_announcements (
            uid TEXT PRIMARY KEY,
            company TEXT,
            category TEXT,
            severity INTEGER,
            headline TEXT,
            seen_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def is_new(conn, uid: str) -> bool:
    cur = conn.execute("SELECT 1 FROM seen_announcements WHERE uid = ?", (uid,))
    return cur.fetchone() is None


def mark_seen(conn, uid, company, category, severity, headline):
    conn.execute(
        "INSERT OR IGNORE INTO seen_announcements "
        "(uid, company, category, severity, headline, seen_at) VALUES (?, ?, ?, ?, ?, ?)",
        (uid, company, category, severity, headline, datetime.utcnow().isoformat()),
    )
    conn.commit()


def todays_alerts(conn):
    """All alerts stored today (UTC date), used for the 6 PM summary."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cur = conn.execute(
        "SELECT company, category, severity, headline, seen_at FROM seen_announcements "
        "WHERE seen_at LIKE ? ORDER BY seen_at",
        (f"{today}%",),
    )
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Classification: keyword -> (category, severity stars 1-5)
# Order matters - first match wins. Tune this list as you learn what BSE
# actually sends for this company.
# ---------------------------------------------------------------------------

RULES = [
    (["preferential allot", "preferential issue"], "Preferential Allotment", 5),
    (["rights issue"], "Rights Issue", 5),
    (["bonus issue", "stock split", "sub-division", "subdivision of shares"], "Bonus / Split", 5),
    (["pledge", "encumbrance", "revoke of pledge", "release of pledge"], "Promoter Pledge/Release", 5),
    (["insider trading", "sast", "regulation 7", "trading window"], "Insider Trading", 4),
    (["bulk deal"], "Bulk Deal", 4),
    (["block deal"], "Block Deal", 4),
    (["shareholding", "regulation 29", "regulation 31", "regulation 30 - change in"], "Promoter Shareholding", 4),
    (["credit rating"], "Credit Rating Change", 3),
    (["board meeting", "outcome of board"], "Board Meeting", 3),
    (["order", "work order", "award of", "contract", "lois", "letter of intent"], "Order Win", 4),
    (["agm", "annual general meeting"], "AGM/EGM Notice", 2),
    (["financial result", "quarterly result", "unaudited", "audited"], "Financial Results", 3),
]

DEFAULT_CATEGORY = "General Announcement"
DEFAULT_SEVERITY = 2


def classify(text: str):
    """text = combined headline + category + subject fields, lowercased."""
    t = text.lower()
    for keywords, category, severity in RULES:
        if any(kw in t for kw in keywords):
            return category, severity
    return DEFAULT_CATEGORY, DEFAULT_SEVERITY


def stars(n: int) -> str:
    n = max(1, min(5, n))
    return "★" * n + "☆" * (5 - n)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram(message: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured - skipping send. Message was:\n%s", message)
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, data=payload, timeout=15)
        if r.status_code != 200:
            log.error("Telegram send failed [%s]: %s", r.status_code, r.text)
            return False
        return True
    except requests.RequestException as e:
        log.error("Telegram request error: %s", e)
        return False


# ---------------------------------------------------------------------------
# Email backup
# ---------------------------------------------------------------------------

def send_email(subject: str, body: str) -> bool:
    if not config.EMAIL_ENABLED:
        return False
    if not (config.EMAIL_USER and config.EMAIL_PASS and config.EMAIL_TO):
        log.warning("Email enabled but credentials missing - skipping.")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_USER
    msg["To"] = config.EMAIL_TO

    try:
        with smtplib.SMTP(config.EMAIL_HOST, config.EMAIL_PORT, timeout=20) as server:
            server.starttls()
            server.login(config.EMAIL_USER, config.EMAIL_PASS)
            server.sendmail(config.EMAIL_USER, [config.EMAIL_TO], msg.as_string())
        return True
    except Exception as e:
        log.error("Email send error: %s", e)
        return False


def escape_html(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
