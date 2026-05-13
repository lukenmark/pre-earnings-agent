# Pre-Earnings Research Agent

An autonomous stock research system that monitors small-cap equities before earnings, scores them across 8 factors, fires Telegram alerts, and runs a Streamlit dashboard — all on your Mac.

---

## How it works

1. **Discovery scan** — Finviz screener finds candidates 21+ days from earnings
2. **Four checkpoints** (T-21, T-14, T-7, T-3) — each runs 8 scoring factors via Claude
3. **Score + decision** — composite 0–100, decision BUY / WATCH / NO_GO
4. **Telegram alert** — sent at T-3 for BUY decisions
5. **Dashboard** — Streamlit UI shows watchlist, checkpoint history, feedback, insights

---

## Setup

### 1. Clone and install

```bash
cd tools/pre-earnings-agent
pip install -r requirements.txt
```

### 2. Configure `.env`

Copy the example and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | Yes | Token from @BotFather |
| `TELEGRAM_GROUP_CHAT_ID` | Yes | Chat ID of your Telegram group |
| `TELEGRAM_ALLOWED_USER_IDS` | No | Comma-separated user IDs for DM access |
| `DATABASE_URL` | No | SQLite path (default: `sqlite:///./research.db`) |
| `LLM_DEFAULT_MODEL` | No | Default Claude model (default: `claude-sonnet-4-6`) |
| `LLM_FALLBACK_MODEL` | No | Fallback model (default: `claude-haiku-4-5-20251001`) |
| `FINVIZ_SCREEN_LIMIT` | No | Max candidates per scan (default: 20) |
| `NEWS_PROVIDER` | No | `yfinance` (default) |
| `OPTIONS_PROVIDER` | No | `estimated` (default) |
| `INDUSTRY_PROVIDER` | No | `yfinance` (default) |
| `DASHBOARD_PASSWORD` | No | Shared password for Streamlit login |

**Getting your Telegram chat ID:**
1. Add your bot to the group
2. Send a message in the group
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and look for `"chat":{"id":`

### 3. Initialize the database

```bash
python run.py status
```

This auto-creates `research.db` on first run.

---

## Running

### All CLI commands

```bash
python run.py scan                    # Run discovery scan, add new candidates
python run.py analyze AAPL            # Run T-21 checkpoint on a ticker
python run.py checkpoint AAPL T-14    # Run a specific checkpoint
python run.py bot                     # Start Telegram bot only
python run.py start                   # Start bot + scheduler together
python run.py dashboard               # Launch Streamlit dashboard
python run.py feedback AAPL           # Add 1-5 star feedback for a ticker
python run.py status                  # Show scheduler state + watchlist count
```

### First run

```bash
# 1. Initialize and scan for candidates
python run.py scan

# 2. Manually analyze a ticker
python run.py analyze NVDA

# 3. Start the full system
python run.py start
```

---

## tmux guide

Run the agent + dashboard + logs in three persistent windows:

```bash
bash deploy/tmux_start.sh
```

This creates a session named `pre-earnings` with:
- Window `agent` — `python run.py start`
- Window `dashboard` — `python run.py dashboard`
- Window `logs` — `tail -f logs/agent.log`

**tmux key reference:**

| Key | Action |
|---|---|
| `tmux attach -t pre-earnings` | Attach to the session |
| `Ctrl+B, D` | Detach (leaves agent running) |
| `Ctrl+B, N` | Next window |
| `Ctrl+B, P` | Previous window |
| `Ctrl+B, W` | Show all windows |
| `tmux kill-session -t pre-earnings` | Stop everything |

---

## launchd setup (auto-start on login)

The plist at `deploy/pre-earnings-agent.plist` starts the agent automatically on macOS login.

### Install

```bash
# Copy plist to LaunchAgents
cp deploy/pre-earnings-agent.plist ~/Library/LaunchAgents/

# Load it (starts immediately)
launchctl load ~/Library/LaunchAgents/com.morConsulting.pre-earnings-agent.plist
```

**Intel Mac:** Edit the plist first — change `/opt/homebrew/bin/python3` to `/usr/local/bin/python3`.

### Manage

```bash
# Check status
launchctl list | grep pre-earnings

# Stop
launchctl unload ~/Library/LaunchAgents/com.morConsulting.pre-earnings-agent.plist

# Restart
launchctl unload ~/Library/LaunchAgents/com.morConsulting.pre-earnings-agent.plist
launchctl load ~/Library/LaunchAgents/com.morConsulting.pre-earnings-agent.plist

# View logs
tail -f tools/pre-earnings-agent/logs/agent.log
tail -f tools/pre-earnings-agent/logs/errors.log
```

### Note on launchd vs tmux

| | launchd | tmux |
|---|---|---|
| Auto-starts on login | Yes | No |
| Restart on crash | Yes | No |
| Interactive log tailing | No | Yes |
| Dashboard access | No | Yes |
| Best for | Production | Development |

Use **launchd** for the background agent in production. Use **tmux** when developing or when you also want the dashboard running.

---

## Adding a second user

The agent supports multiple Telegram users via the allowlist:

1. Have the second user message the bot directly (`/start`)
2. Get their user ID: visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Add to `.env`:
   ```
   TELEGRAM_ALLOWED_USER_IDS=111111111,222222222
   ```
4. Restart the agent

Alternatively, add them to the same Telegram group that `TELEGRAM_GROUP_CHAT_ID` points to — the group auth check will cover them automatically.

---

## Swapping data providers

Providers are set via `.env`. Each key maps to a module in `data/providers/`.

### Options provider

| Value | Description |
|---|---|
| `estimated` (default) | Estimates IV from price history — no API key needed |

To add a real options provider:
1. Create `data/providers/my_options.py` implementing `OptionsProviderBase`
2. Register it in `data/factory.py`
3. Set `OPTIONS_PROVIDER=my_options` in `.env`

### News provider

| Value | Description |
|---|---|
| `yfinance` (default) | Free, no key |

### Industry provider

| Value | Description |
|---|---|
| `yfinance` (default) | Free, no key |

---

## Running tests

```bash
# All tests
python -m pytest

# Storage layer only (fast, no network)
python -m pytest tests/test_storage/ -v

# Scoring tests
python -m pytest tests/test_scoring/ -v
```

---

## Troubleshooting

**Bot not responding**
- Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_GROUP_CHAT_ID` are set in `.env`
- Confirm the bot is a member of the group
- Check logs: `tail -f logs/errors.log`

**`ModuleNotFoundError`**
- Run `pip install -r requirements.txt` from inside the `pre-earnings-agent/` directory

**`ANTHROPIC_API_KEY` error**
- The `.env` file must be in the project root (`pre-earnings-agent/.env`)
- Confirm `load_dotenv()` runs before any module import (it does in `run.py`)

**SQLite `OperationalError: no such table`**
- Run `python run.py status` once to initialize the schema

**Scheduler jobs not running**
- The scheduler only runs when started with `python run.py start` (not `bot`)
- Check `python run.py status` to see next run times

**launchd not starting**
- Verify the Python path in the plist matches your install (`which python3`)
- Check `~/Library/Logs/com.morConsulting.pre-earnings-agent.log` for launchd errors
- Confirm the `.env` file exists in the project directory (launchd doesn't source shell profiles)

**Dashboard blank / login loop**
- Set `DASHBOARD_PASSWORD` in `.env`
- Run dashboard directly: `streamlit run dashboard/app.py`

---

## Project structure

```
pre-earnings-agent/
├── run.py                  # CLI entry point
├── requirements.txt
├── .env.example
├── alembic.ini
├── alembic/                # DB migrations
├── core/
│   ├── analysis/           # Financial deep dive, MBP, news tiering, share structure
│   ├── scoring/            # 8 factor scorers + composite
│   └── decisions.py        # BUY / WATCH / NO_GO logic
├── data/
│   ├── providers/          # Swappable data provider implementations
│   ├── finviz_screener.py
│   ├── yfinance_client.py
│   └── cache.py
├── dashboard/
│   ├── app.py
│   └── tabs/               # watchlist, checkpoints, feedback, insights, recommendations
├── models/                 # Pydantic models
├── orchestrator/
│   ├── agent_orchestrator.py
│   ├── scheduler.py        # APScheduler jobs
│   ├── fiscal_calendar.py
│   └── watchlist_manager.py
├── storage/
│   ├── database.py
│   ├── tables.py           # SQLAlchemy ORM
│   └── repositories/       # CRUD per entity
├── telegram_bot/
│   ├── bot.py
│   ├── handlers/           # One file per command
│   └── notifications.py
├── tests/
│   ├── test_scoring/
│   └── test_storage/
├── deploy/
│   ├── tmux_start.sh
│   └── pre-earnings-agent.plist
└── logs/
```
