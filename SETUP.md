# First-Run Setup Guide

Step-by-step. Do these in order.

---

## Step 1 — Get your Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in → **API Keys** → **Create Key**
3. Copy it. You'll paste it into `.env` in Step 4.

---

## Step 2 — Create your Telegram bot

1. Open Telegram, search for **@BotFather**
2. Send: `/newbot`
3. Give it a name (e.g. `Pre Earnings Agent`)
4. Give it a username (e.g. `pre_earnings_luke_bot`) — must end in `bot`
5. BotFather replies with your **bot token** — looks like `7123456789:AAF...`
6. Copy it.

---

## Step 3 — Create a Telegram group and get the chat ID

1. Create a new Telegram group (e.g. `Earnings Alerts`)
2. Add your bot to the group (search by its username)
3. Send any message in the group (e.g. "hello")
4. In a browser, visit:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
   Replace `<YOUR_BOT_TOKEN>` with the token from Step 2.
5. Look for `"chat":{"id":` in the response — the number after it is your **group chat ID**
   - It will be a negative number like `-1001234567890`
6. Copy it.

> **If the response is empty:** Send another message in the group, then refresh the URL.

---

## Step 4 — Configure `.env`

Navigate to the project:
```bash
cd /Users/lukenmark/Documents/claude-os/tools/pre-earnings-agent
cp .env.example .env
```

Open `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...          # from Step 1
TELEGRAM_BOT_TOKEN=7123456789:AAF...  # from Step 2
TELEGRAM_GROUP_CHAT_ID=-1001234567890 # from Step 3
DASHBOARD_PASSWORD=pick_a_password    # anything you want
```

Leave everything else as-is for now.

---

## Step 5 — Install dependencies

```bash
pip install -r requirements.txt
```

This takes about 1-2 minutes.

---

## Step 6 — Initialize and verify

```bash
python run.py status
```

Expected output:
```
Scheduler not running (start with: python run.py start)
Watchlist: 0 active tickers
```

If you see this, the database is initialized and everything is wired up.

---

## Step 7 — Run your first scan

```bash
python run.py scan
```

This hits Finviz, finds small-cap tickers 21+ days from earnings, and adds them to your watchlist. Takes ~30 seconds.

Expected output:
```
✅ Added 8 new candidates:
  TICKER — score 72/100, earnings: 2026-06-15
  ...
```

---

## Step 8 — Analyze a ticker manually (optional)

Pick any ticker from the scan results and run a full T-21 analysis:

```bash
python run.py analyze TICKER
```

This calls Claude and scores all 8 factors. Takes 20-40 seconds. Good way to confirm your Anthropic key works.

---

## Step 9 — Start the full system

```bash
python run.py start
```

This boots the Telegram bot and the scheduler together. You should receive a startup message in your Telegram group.

**Test it:** Open Telegram, go to your group, send `/status` — the bot should respond.

To run it in the background and keep it alive, use tmux:

```bash
bash deploy/tmux_start.sh
```

Then detach: `Ctrl+B, D`

---

## Step 10 — Launch the dashboard (optional)

In a separate terminal (or tmux window):

```bash
python run.py dashboard
```

Opens at `http://localhost:8501`. Log in with the password you set in `.env`.

---

## Auto-start on login (optional)

If you want the agent to start automatically when your Mac boots:

```bash
cp deploy/pre-earnings-agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.morConsulting.pre-earnings-agent.plist
```

**Intel Mac only:** Edit the plist first and change `/opt/homebrew/bin/python3` to `/usr/local/bin/python3`.

To stop: `launchctl unload ~/Library/LaunchAgents/com.morConsulting.pre-earnings-agent.plist`

---

## Laptop setup

```bash
git clone https://github.com/lukenmark/pre-earnings-agent.git
cd pre-earnings-agent
pip install -r requirements.txt
cp .env.example .env
# fill in .env with same keys as above
python run.py status
```

Note: each machine gets its own `research.db` — they don't sync. The laptop is for running analysis and reading output, not for running the scheduler (keep that on the mini).

---

## Quick reference

| Command | What it does |
|---|---|
| `python run.py scan` | Find new candidates |
| `python run.py analyze TICKER` | Full T-21 analysis on a ticker |
| `python run.py start` | Boot bot + scheduler |
| `python run.py dashboard` | Open Streamlit UI |
| `python run.py status` | Show scheduler state + watchlist |
| `python run.py feedback TICKER` | Rate a signal 1-5 stars |
| `bash deploy/tmux_start.sh` | Start everything in tmux |

| Telegram command | What it does |
|---|---|
| `/status` | System health + watchlist count |
| `/watchlist` | Show active tickers |
| `/scan` | Trigger a discovery scan |
| `/analyze TICKER` | Run T-21 on a ticker |
| `/alerts` | Show active BUY alerts |
| `/help` | Full command list |
