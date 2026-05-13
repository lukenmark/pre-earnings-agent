# Pre-Earnings Agent — Project Status Summary

**Date:** 2026-05-13  
**Status:** Phase 7 of 8 complete. Phase 8 (CLI polish + requirements.txt + README) remaining.

---

## Build Phase Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Foundation: models/, storage/, alembic/, utils/logger.py, utils/formatting.py | ✅ Done |
| 2 | Scoring engine: core/scoring/ (8 scorers), core/decisions.py, tests/test_scoring/ | ✅ Done |
| 3 | Data layer: data/ (finviz, yfinance, edgar, news, options, industry, cache), utils/llm.py, utils/prompts.py | ✅ Done |
| 4 | Analysis engine: core/analysis/ (financial_deep_dive, share_structure, mbp, news_tiering), orchestrator/fiscal_calendar.py | ✅ Done |
| 5 | Orchestrator: agent_orchestrator.py, scheduler.py, watchlist_manager.py | ✅ Done |
| 6 | Telegram bot: telegram_bot/ (bot, all handlers, notifications, keyboards), deploy/ (plist + tmux) | ✅ Done |
| 7 | Streamlit dashboard: dashboard/ (app.py + 5 tabs), .streamlit/config.toml | ✅ Done |
| 8 | CLI polish, tests/test_storage/test_repositories.py, requirements.txt, README.md | ⏳ Next |

---

## Architecture Decisions

### Scoring model
- Every scorer returns `FactorScore` (models/scores.py): `.score` int 0-100, `.reasoning` str, `.raw_inputs` dict, `.sources` list[str], `.scored_at` datetime
- Composite weights: news_quality=0.20, price_absorption_gap=0.15, industry_momentum=0.15, revenue_trend=0.15, earnings_profile=0.10, options_flow=0.10, insider_activity=0.10, cash_runway=0.05
- Hard veto (insider selling) fires before any weighted sum — returns (0, "NO_GO") immediately
- Core override: news<40 OR pag<40 → NO_GO; both<50 → NO_GO; core_avg<60 AND composite≥70 → forced WATCH
- BUY threshold: composite ≥ 70. WATCH: 50-69. NO_GO: <50

### Earnings profile dual-track
- Track A (eps_ttm < 0): growth-stage company; scores R&D, capex, pipeline, deferred revenue
- Track B (eps_ttm ≥ 0): profitable; scores margin expansion, EPS growth, consensus beat potential
- eps_ttm = 0.0 → Track B

### Price Absorption Gap (PAG)
- C1 (50%): news-quality-relative price response
- C2 (30%): C1 × suppression multiplier (mechanical=1.2, none_identified=1.4, fundamental=0.5, not_suppressed=1.0)
- C3 (20%): catalyst-remaining (flat/down price = high remaining upside)

### Data provider abstraction
- Python Protocol classes in data/providers/base.py (NewsProvider, OptionsFlowProvider, IndustryDataProvider)
- Factory in data/factory.py reads NEWS_PROVIDER / OPTIONS_PROVIDER / INDUSTRY_PROVIDER from .env
- Active providers: yfinance_news, estimated_options, yfinance_industry

### SQLAlchemy session safety
- Critical pattern: always extract all ORM row attributes inside `with get_db() as db:` block
- Never access `.attribute` on an ORM row after the session closes → DetachedInstanceError
- Repositories use eager extraction; orchestrator extracts prior_composite inside same context manager

### LLM client
- Default: `claude-sonnet-4-6`. Fallback: `claude-haiku-4-5-20251001`
- Prompt caching via `cache_control: {"type": "ephemeral"}` on system prompts
- Logs tokens + USD cost per operation (COST_PER_MTok table in utils/llm.py)
- Retry on 429 via tenacity

### Fiscal calendar
- Non-calendar fiscal years handled via FiscalCalendar (orchestrator/fiscal_calendar.py)
- `get_quarter_for_date()` and `get_prior_quarter()` use relativedelta for correct boundaries
- Example: SNOW (FY ends Jan 31), Mar 1 2026 → FQ1 FY2027 (Feb 1–May 2)

### Checkpoint schedule
- T-21: Full analysis including MBP, financial deep-dive, all 8 scorers
- T-14, T-7: Refresh financial deep-dive + all scorers except insider (neutral placeholder) + options (neutral)
- T-3: All 8 scorers with real insider (Form 4) + real options flow data
- APScheduler jobs: Mon/Wed/Fri 6AM ET discovery; weekdays 7AM ET checkpoint; Sunday 5AM ET earnings refresh

### Telegram bot
- aiogram 3.x, multi-user group chat via TELEGRAM_GROUP_CHAT_ID env var
- AuthFilter checks group chat ID or individual user IDs from TELEGRAM_ALLOWED_USER_IDS
- All heavy handlers use `run_in_executor` to avoid blocking the event loop
- Commands: /watchlist /scan /analyze /checkpoint /alerts /feedback /help /status

### Dashboard
- Streamlit, password auth via DASHBOARD_PASSWORD env var
- Dark theme (.streamlit/config.toml: base="dark", primaryColor="#4dabf7"), headless=true, port=8501
- 5 tabs: Watchlist, Recommendations, Checkpoints (Plotly trajectory charts), Feedback, Insights
- Plotly charts require unique `key=` per chart to avoid duplicate-widget errors

### Deployment
- Mac Mini: launchd plist at deploy/pre-earnings-agent.plist, /opt/homebrew/bin/python3 (Apple Silicon)
- Dev/manual: deploy/tmux_start.sh (3 windows: agent, dashboard, log tail)

---

## Known Limitations / TODOs

- `datetime.utcnow()` deprecation warnings on Python 3.14 — harmless, clean up in future pass
- Finviz free tier doesn't return debt_equity / inst_own_pct — treated as None (neutral) in penalty scoring
- Google News RSS secondary source degrades gracefully on Python 3.14 (BeautifulSoup XML parser issue) — yfinance is primary news source
- tests/test_storage/test_repositories.py is empty (placeholder __init__.py only) — to be filled in Phase 8
- requirements.txt not yet written (Phase 8)
- README.md not yet written (Phase 8)

---

## Key File Locations

```
pre-earnings-agent/
├── models/          # Pydantic v2: scores.py, watchlist.py, checkpoint.py, alert.py, industry.py, mbp.py
├── storage/         # SQLAlchemy ORM: database.py, tables.py, repositories/
├── core/
│   ├── scoring/     # 8 scorers + composite.py + decisions.py
│   └── analysis/    # financial_deep_dive.py, news_tiering.py, share_structure.py, mbp.py
├── data/            # Fetchers: yfinance_client, edgar_client, finviz_screener, news_fetcher, options_fetcher, industry_fetcher
│   └── providers/   # Protocol-based abstraction: base.py + yfinance_news, estimated_options, yfinance_industry
├── orchestrator/    # agent_orchestrator.py, scheduler.py, watchlist_manager.py, fiscal_calendar.py
├── telegram_bot/    # bot.py, handlers/, notifications.py, keyboards.py
├── dashboard/       # app.py, tabs/ (5 tabs)
├── utils/           # llm.py, prompts.py, logger.py, formatting.py
├── tests/
│   ├── test_scoring/  # 8 scorer unit tests (all passing)
│   └── test_storage/  # Placeholder — Phase 8
├── deploy/          # pre-earnings-agent.plist, tmux_start.sh
├── alembic/         # versions/001_initial_schema.py
├── run.py           # CLI: scan, analyze, checkpoint, bot, start, dashboard, feedback, status
├── .env.example
├── alembic.ini
└── research.db      # SQLite (dev)
```

---

## Phase 8 Checklist

- [ ] `tests/test_storage/test_repositories.py` — CRUD round-trips on in-memory SQLite for all 5 repos
- [ ] `requirements.txt` — pinned versions (Python 3.11+ compatible, tested on 3.14)
- [ ] `README.md` — setup + deployment guide (Mac Mini launchd + optional VPS)
- [ ] Run Lens review (per CLAUDE.md: always run Lens before launch)
