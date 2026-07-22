# 📈 StockAlertBot — Dharan Infra-EPC Corporate Announcement Monitor

An automated monitor that watches BSE/NSE corporate filings for **Dharan Infra-EPC
Limited** (BSE: 541161, NSE: DHARAN) and sends real-time Telegram alerts for
promoter shareholding changes, pledges, bulk/block deals, board meetings,
order wins, credit rating changes, and more — running for free on GitHub Actions.

## How it works

1. GitHub Actions triggers `main.py` every hour (cron job, no server needed).
2. `main.py` calls BSE India's public corporate-announcements API (via the
   [`bse`](https://pypi.org/project/bse/) Python package) for each company in
   `companies.json`.
3. Every announcement is classified into a category and an "impact" score
   (1–5 stars) using keyword rules in `utils.py`.
4. New announcements (not seen before, tracked in `database.db`) are sent to
   your Telegram, and optionally emailed for high-impact ones.
5. A second workflow trigger fires once a day at 6 PM IST and sends a summary
   of everything caught that day.

## Project structure

```
StockAlertBot/
├── main.py                          # entry point: monitor + summary logic
├── config.py                        # settings, reads secrets from env vars
├── utils.py                         # SQLite dedup, classifier, Telegram/email senders
├── companies.json                   # your watchlist
├── requirements.txt
├── .env.example                     # template for local testing
├── database.db                      # created automatically on first run
└── .github/workflows/stock-alert.yml # the automation schedule
```

---

## Step-by-step setup

### 1. Create your Telegram bot

1. Open Telegram, search for **@BotFather**, and send `/newbot`.
2. Give it a name and a username (must end in `bot`, e.g. `DharanAlertsBot`).
3. BotFather replies with a token like `123456789:AAExxxxxxxxxxxxxxxxxxxxxxx`.
   Save it — this is your `TELEGRAM_BOT_TOKEN`.
4. Send your new bot any message (e.g. "hi") so it can message you back.
5. Get your chat ID: open this URL in your browser (replace `<TOKEN>`):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Look for `"chat":{"id":123456789,...}` in the response — that number is
   your `TELEGRAM_CHAT_ID`.

### 2. Push this project to a GitHub repo

```bash
cd StockAlertBot
git init
git add .
git commit -m "Initial commit: StockAlertBot"
git branch -M main
git remote add origin https://github.com/<your-username>/StockAlertBot.git
git push -u origin main
```

### 3. Add your secrets to GitHub

In your repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add at minimum:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from step 1 |
| `TELEGRAM_CHAT_ID` | from step 1 |

Optional (only if you want email backup — see step 5):
`EMAIL_ENABLED`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASS`, `EMAIL_TO`.

### 4. Enable the workflow

Go to the **Actions** tab of your repo → you should see "Stock Alert Bot" →
click **Enable workflow** if prompted. Then click **Run workflow** once to
test it manually instead of waiting for the next hour.

### 5. (Optional) Email backup via Gmail

1. Turn on 2-Step Verification on your Google account.
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   and generate an "App Password" (16 characters, no spaces).
3. Set `EMAIL_ENABLED=true`, `EMAIL_USER` = your Gmail address, `EMAIL_PASS` =
   that app password, `EMAIL_TO` = wherever you want the backup sent.
4. Only alerts with severity ≥ `EMAIL_MIN_SEVERITY` (default 4★) get emailed,
   so your inbox isn't flooded — Telegram remains the primary channel.

### 6. Test locally first (recommended before relying on Actions)

```bash
pip install -r requirements.txt
cp .env.example .env      # then fill in your real token/chat id
python main.py --debug    # prints the raw JSON BSE returns - sanity check
python main.py            # runs one real monitoring pass
```

> **Why `--debug` matters:** BSE's corporate-announcements API is public but
> unofficial and undocumented — field names occasionally shift. Run
> `--debug` once after setup and skim the printed JSON keys against the
> `first_present(...)` lists in `main.py`. If a field name has changed,
> just add the new spelling to the relevant list — no other code changes
> needed.

---

## Adding more companies

Edit `companies.json`:

```json
[
  { "name": "Dharan Infra-EPC Ltd", "bse_code": "541161", "nse_symbol": "DHARAN" },
  { "name": "Some Other Company",   "bse_code": "500XXX", "nse_symbol": "SYMBOL" }
]
```

Find a company's BSE code on bseindia.com's search, or via
`bse.getScripCode("company name")` from the `bse` package.

## Tuning alert severity / categories

All classification logic is in `utils.py` → `RULES`. Each rule is
`(keywords, category_label, severity_1_to_5)`; the first matching rule wins.
Add keywords as you observe real announcements come through.

## Changing the check frequency

Edit the cron expression in `.github/workflows/stock-alert.yml`. GitHub's
minimum interval is roughly 5 minutes, but for a free account hourly
(`0 * * * *`) is the realistic sustainable option — GitHub may delay or skip
runs during high load regardless of what you set. For near-real-time
alerts, run the same `main.py` via cron on a Raspberry Pi or a small VPS
instead (see the "Deployment" note below).

## Deployment options

- **GitHub Actions (this repo, default):** free, no server, hourly checks,
  runs even when your laptop is off. Best for a portfolio project.
- **Raspberry Pi / VPS:** add `main.py` to a system crontab running every
  5–10 minutes for closer to real-time alerts. Same code, no changes needed
  — just point a cron job at `python3 main.py` and keep the `.env` file
  alongside it instead of GitHub Secrets.

## Notes & disclaimer

- This uses BSE India's **public** website API through the unofficial
  `bse` Python package — the same data bseindia.com's own pages use. There's
  no guarantee of uptime or unchanged field names since it's not an official
  developer API; that's exactly why `--debug` mode and the fallback field
  lists exist.
- This tool is for informational/educational tracking only — it is not
  investment advice, and you should always verify any announcement against
  the original BSE/NSE filing before acting on it.
