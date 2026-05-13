import streamlit as st
from datetime import datetime


@st.cache_data(ttl=60)
def load_feedback():
    from storage.database import get_db
    from storage.repositories.feedback_repo import get_all
    items = []
    with get_db() as db:
        rows = get_all(db)
        for row in rows:
            items.append({
                "ticker": row.ticker,
                "user_id": row.user_id,
                "rating": row.rating,
                "notes": row.notes or "",
                "created_at": row.created_at,
            })
    return sorted(items, key=lambda x: x["created_at"] or datetime.min, reverse=True)


def render():
    st.title("💬 My Feedback")

    items = load_feedback()

    if not items:
        st.info("No feedback yet. Use `/feedback TICKER` in Telegram to rate outcomes.")
        return

    # Summary stats
    col1, col2, col3 = st.columns(3)
    avg_rating = sum(i["rating"] for i in items if i["rating"]) / max(len(items), 1)
    tickers_rated = len({i["ticker"] for i in items})
    five_stars = sum(1 for i in items if i["rating"] == 5)
    col1.metric("Total Feedback Entries", len(items))
    col2.metric("Tickers Rated", tickers_rated)
    col3.metric("Avg Rating", f"{avg_rating:.1f} ⭐")

    st.markdown("---")

    # Filter
    all_tickers = sorted({i["ticker"] for i in items})
    filter_ticker = st.selectbox("Filter by ticker", ["All"] + all_tickers)

    filtered = items if filter_ticker == "All" else [i for i in items if i["ticker"] == filter_ticker]

    # Table
    for item in filtered:
        stars = "⭐" * (item["rating"] or 0)
        date_str = str(item["created_at"])[:16] if item["created_at"] else "—"
        notes_text = f" — {item['notes']}" if item["notes"] else ""
        user_text = f"User {item['user_id'][:8]}" if item["user_id"] else "unknown"

        st.markdown(
            f"**{item['ticker']}** &nbsp; {stars} &nbsp; `{date_str}` &nbsp; *{user_text}*{notes_text}"
        )

    st.markdown("---")

    # Add feedback form
    st.subheader("Add Feedback")
    col1, col2 = st.columns([2, 1])
    with col1:
        new_ticker = st.text_input("Ticker", placeholder="NVDA").upper()
        notes_input = st.text_area("Notes (optional)", height=80)
    with col2:
        rating_input = st.select_slider("Rating", options=[1, 2, 3, 4, 5], value=3)
        st.markdown(f"{'⭐' * rating_input}")
        if st.button("Save Feedback", use_container_width=True) and new_ticker:
            from storage.database import get_db
            from storage.repositories.feedback_repo import save as save_fb
            with get_db() as db:
                save_fb(db, new_ticker, "dashboard_user", rating_input, notes_input or None)
            st.success(f"✅ Feedback saved for {new_ticker}")
            st.cache_data.clear()
            st.rerun()
