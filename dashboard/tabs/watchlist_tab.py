import streamlit as st
from datetime import date
import json


@st.cache_data(ttl=60)
def load_watchlist_data():
    from storage.database import get_db
    from storage.repositories.watchlist_repo import get_all_active
    from storage.repositories.checkpoint_repo import get_latest, get_trajectory
    rows = []
    with get_db() as db:
        active = get_all_active(db)
        for row in active:
            latest = get_latest(db, row.ticker)
            traj = get_trajectory(db, row.ticker)
            rows.append({
                "ticker": row.ticker,
                "company": row.company_name,
                "status": row.status,
                "earnings_date": row.earnings_date,
                "fiscal_year_end": row.fiscal_year_end,
                "industry": row.industry or "—",
                "eps_ttm": row.eps_ttm,
                "market_cap": row.market_cap,
                "notes": row.notes or "",
                "date_added": row.date_added,
                "score": latest.composite_score if latest else None,
                "decision": latest.decision if latest else None,
                "last_checkpoint": latest.checkpoint if latest else None,
                "last_checkpoint_date": latest.created_at if latest else None,
                "hard_veto": latest.hard_veto if latest else False,
                "flags": json.loads(latest.report_json).get("flags", []) if latest and latest.report_json else [],
                "trajectory": traj,
            })
    return rows


def _score_color(score):
    if score is None:
        return "#6c757d"
    if score >= 70:
        return "#28a745"
    if score >= 50:
        return "#ffc107"
    return "#dc3545"


def _days_until_earnings(earnings_date) -> int | None:
    if not earnings_date:
        return None
    today = date.today()
    if isinstance(earnings_date, str):
        earnings_date = date.fromisoformat(earnings_date)
    return (earnings_date - today).days


def _next_checkpoint_label(earnings_date) -> str:
    days = _days_until_earnings(earnings_date)
    if days is None:
        return "No earnings date"
    if days > 21:
        return f"T-21 in {days - 21}d"
    if days > 14:
        return f"T-14 in {days - 14}d"
    if days > 7:
        return f"T-7 in {days - 7}d"
    if days > 3:
        return f"T-3 in {days - 3}d"
    if days >= 0:
        return f"⚡ Earnings in {days}d"
    return "Earnings passed"


def render():
    st.title("📋 Active Watchlist")

    rows = load_watchlist_data()

    if not rows:
        st.info("Watchlist is empty. Use `/scan` in Telegram or `python run.py scan` to discover candidates.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    buy_count = sum(1 for r in rows if r["decision"] == "BUY")
    watch_count = sum(1 for r in rows if r["decision"] == "WATCH")
    no_go_count = sum(1 for r in rows if r["decision"] == "NO_GO")
    unscored = sum(1 for r in rows if r["score"] is None)
    col1.metric("Total Active", len(rows))
    col2.metric("🟢 BUY", buy_count)
    col3.metric("🟡 WATCH", watch_count)
    col4.metric("🔴 NO-GO / Unscored", no_go_count + unscored)

    st.markdown("---")

    # Filter controls
    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        search = st.text_input("🔍 Filter by ticker or company", placeholder="NVDA, Apple, etc.")
    with filter_col2:
        status_filter = st.selectbox("Status", ["All", "candidate", "active", "buy_alert", "no_go"])

    # Filter rows
    filtered = rows
    if search:
        s = search.upper()
        filtered = [r for r in filtered if s in r["ticker"] or s in r["company"].upper()]
    if status_filter != "All":
        filtered = [r for r in filtered if r["status"] == status_filter]

    # Sort: by earnings date (soonest first), then unscored last
    filtered.sort(key=lambda r: (
        r["earnings_date"] or date(2099, 1, 1),
        -(r["score"] or -1),
    ))

    # Cards
    for row in filtered:
        score = row["score"]
        color = _score_color(score)
        days = _days_until_earnings(row["earnings_date"])
        next_cp = _next_checkpoint_label(row["earnings_date"])

        score_text = f"{score}/100" if score is not None else "Not scored"
        decision_text = row["decision"] or "—"
        earnings_text = str(row["earnings_date"]) if row["earnings_date"] else "TBD"
        mc_text = ""
        if row["market_cap"]:
            mc = row["market_cap"]
            if mc >= 1e9:
                mc_text = f"${mc/1e9:.1f}B"
            elif mc >= 1e6:
                mc_text = f"${mc/1e6:.0f}M"

        veto_badge = " 🚫 HARD VETO" if row["hard_veto"] else ""

        with st.container():
            st.markdown(
                f"""
                <div style="border-left: 4px solid {color}; padding: 12px 16px; margin: 8px 0;
                            background: #1e1e1e; border-radius: 4px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:1.1em; font-weight:bold; color:#fff;">
                            {row['ticker']}{veto_badge}
                        </span>
                        <span style="color:{color}; font-weight:bold; font-size:1.1em;">
                            {score_text}
                        </span>
                    </div>
                    <div style="color:#aaa; font-size:0.9em; margin-top:4px;">
                        {row['company']} &nbsp;|&nbsp; {row['industry']}
                        {f'&nbsp;|&nbsp; {mc_text}' if mc_text else ''}
                    </div>
                    <div style="margin-top:8px; display:flex; gap:16px; font-size:0.85em; color:#ccc;">
                        <span>Decision: <b style="color:{color};">{decision_text}</b></span>
                        <span>Earnings: <b>{earnings_text}</b> ({days}d)</span>
                        <span>Next: <b>{next_cp}</b></span>
                        <span>Last CP: {row['last_checkpoint'] or '—'}</span>
                    </div>
                    {f'<div style="color:#ffc107; font-size:0.8em; margin-top:4px;">⚠️ {row["flags"][0]}</div>' if row.get("flags") else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )

    if not filtered:
        st.info("No tickers match the current filter.")
