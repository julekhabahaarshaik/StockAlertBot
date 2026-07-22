"""
main.py
-------
Run modes:
  python main.py            -> check for new announcements, send alerts
  python main.py --summary  -> send the 6 PM daily summary of today's alerts
  python main.py --debug    -> print raw API fields for the first company
                                (use this once to confirm field names, see README)

This uses the `bse` package (pip install bse), an unofficial but actively
maintained wrapper around BSE India's public corpfiling API. No API key
needed - it's the same data bseindia.com's own website uses.
"""

import json
import sys
from datetime import datetime, timedelta

from bse import BSE

import config
import utils

log = utils.log


def load_companies():
    with open(config.COMPANIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def first_present(d: dict, keys, default=""):
    """Return the first non-empty value found among possible key names.
    BSE's API field names aren't officially documented and can vary
    slightly, so we check several common spellings."""
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


def announcement_uid(item: dict) -> str:
    """A stable unique ID for a single announcement, for dedup purposes."""
    news_id = first_present(item, ["NEWSID", "NEWS_ID", "NewsID"])
    if news_id:
        return str(news_id)
    # Fallback: hash of scrip + date + headline if BSE ever omits NEWSID
    scrip = first_present(item, ["SCRIP_CD", "SCRIPCODE"])
    dt = first_present(item, ["NEWS_DT", "News_DT", "DT_TM"])
    head = first_present(item, ["HEADLINE", "NEWSSUB"])
    return f"{scrip}-{dt}-{head}"


def attachment_url(item: dict) -> str:
    """Best-effort link to the PDF attachment / full announcement."""
    for key in ["ATTACHMENTNAME", "Attachname", "MORE", "NSURL"]:
        val = item.get(key)
        if val:
            if str(val).startswith("http"):
                return val
            return f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{val}"
    scrip = first_present(item, ["SCRIP_CD", "SCRIPCODE"])
    return f"https://www.bseindia.com/stock-share-price/-/-/-/{scrip}/corp-announcements/"


def format_alert(company_name: str, item: dict) -> tuple[str, str, int]:
    headline = first_present(item, ["HEADLINE", "NEWSSUB", "Headline"])
    category_raw = first_present(item, ["CATEGORYNAME", "SUBCATNAME", "Category"])
    news_dt = first_present(item, ["NEWS_DT", "News_DT", "DT_TM"])

    combined_text = f"{headline} {category_raw}"
    category, severity = utils.classify(combined_text)

    time_str = news_dt
    try:
        # BSE usually returns e.g. 2026-07-09T10:42:00
        time_str = datetime.fromisoformat(news_dt).strftime("%d %b %Y, %I:%M %p")
    except Exception:
        pass

    link = attachment_url(item)
    h = utils.escape_html

    message = (
        f"🚨 <b>NEW CORPORATE ANNOUNCEMENT</b>\n\n"
        f"<b>Company:</b> {h(company_name)}\n"
        f"<b>Time:</b> {h(time_str)}\n"
        f"<b>Category:</b> {h(category)}\n"
        f"<b>Title:</b> {h(headline)}\n\n"
        f"<b>Link:</b> {link}\n\n"
        f"<b>Impact:</b> {utils.stars(severity)}"
    )
    return message, category, severity


def check_company(bse_client: BSE, conn, company: dict):
    name = company["name"]
    bse_code = company["bse_code"]

    from_date = datetime.now() - timedelta(days=config.LOOKBACK_DAYS_FIRST_RUN)

    try:
        data = bse_client.announcements(scripcode=bse_code, from_date=from_date)
    except Exception as e:
        log.error("Failed to fetch announcements for %s (%s): %s", name, bse_code, e)
        return

    rows = data.get("Table", []) if isinstance(data, dict) else []
    if not rows:
        log.info("%s: no announcements in lookback window.", name)
        return

    new_count = 0
    for item in rows:
        uid = announcement_uid(item)
        if not utils.is_new(conn, uid):
            continue

        message, category, severity = format_alert(name, item)
        sent = utils.send_telegram(message)
        log.info("[%s] New: %s | %s (%s) | telegram_sent=%s",
                  name, category, first_present(item, ["HEADLINE", "NEWSSUB"]), uid, sent)

        if severity >= config.EMAIL_MIN_SEVERITY:
            utils.send_email(f"[{name}] {category}", message.replace("<b>", "").replace("</b>", ""))

        utils.mark_seen(conn, uid, name, category, severity,
                         first_present(item, ["HEADLINE", "NEWSSUB"]))
        new_count += 1

    log.info("%s: %d new announcement(s) processed.", name, new_count)


def run_debug():
    """One-off helper: prints the raw JSON keys BSE returns, so you can
    confirm/adjust the field names used in format_alert() above."""
    companies = load_companies()
    if not companies:
        print("companies.json is empty.")
        return
    company = companies[0]
    with BSE(download_folder=str(config.BASE_DIR)) as bse_client:
        data = bse_client.announcements(
            scripcode=company["bse_code"],
            from_date=datetime.now() - timedelta(days=7),
        )
    rows = data.get("Table", [])
    print(f"Got {len(rows)} announcement(s) in the last 7 days for {company['name']}.")
    if rows:
        print("\nRaw fields of the first announcement:\n")
        print(json.dumps(rows[0], indent=2, ensure_ascii=False))


def run_summary():
    conn = utils.get_connection()
    rows = utils.todays_alerts(conn)
    if not rows:
        message = "📋 <b>Daily Summary</b>\n\nNo new announcements were detected today."
    else:
        by_company = {}
        for company, category, severity, headline, seen_at in rows:
            by_company.setdefault(company, []).append((category, severity, headline))

        lines = ["📋 <b>Daily Summary</b>", f"Total alerts today: {len(rows)}", ""]
        for company, items in by_company.items():
            lines.append(f"<b>{utils.escape_html(company)}</b> ({len(items)})")
            for category, severity, headline in items:
                lines.append(f"  {utils.stars(severity)} {utils.escape_html(category)} — {utils.escape_html(headline)}")
            lines.append("")
        message = "\n".join(lines)

    utils.send_telegram(message)
    conn.close()


def run_monitor():
    companies = load_companies()
    if not companies:
        log.warning("companies.json is empty - nothing to monitor.")
        return

    conn = utils.get_connection()
    with BSE(download_folder=str(config.BASE_DIR)) as bse_client:
        for company in companies:
            check_company(bse_client, conn, company)
    conn.close()


if __name__ == "__main__":
    if "--debug" in sys.argv:
        run_debug()
    elif "--summary" in sys.argv:
        run_summary()
    else:
        run_monitor()
