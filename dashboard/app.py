import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

# Bridge Streamlit Cloud secrets into os.environ (no-op when running locally)
try:
    for k, v in st.secrets.items():
        if k not in os.environ:
            os.environ[k] = str(v)
except Exception:
    pass

from storage.database import init_db

st.set_page_config(
    page_title="Pre-Earnings Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth ─────────────────────────────────────────────────────

def check_auth() -> bool:
    """Simple shared-password auth. Returns True if authenticated."""
    password = os.getenv("DASHBOARD_PASSWORD", "")
    if not password:
        return True  # No password configured → open access (local-only assumed)

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("📈 Pre-Earnings Research Agent")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("Password", type="password", placeholder="Enter dashboard password")
        if st.button("Login", use_container_width=True):
            if pwd == password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
    return False


# ── Main ─────────────────────────────────────────────────────

def main():
    init_db()

    if not check_auth():
        return

    # Sidebar
    st.sidebar.title("📈 Pre-Earnings Agent")
    st.sidebar.markdown("---")

    tab_names = [
        "📋 Watchlist",
        "🟢 Recommendations",
        "📊 Checkpoints",
        "💬 Feedback",
        "🧠 Insights",
    ]
    tab = st.sidebar.radio("Navigation", tab_names, label_visibility="collapsed")

    st.sidebar.markdown("---")
    st.sidebar.caption("Auto-refreshes every 60s via cache TTL")
    if st.sidebar.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    # Route to tab
    if tab == tab_names[0]:
        from dashboard.tabs.watchlist_tab import render
        render()
    elif tab == tab_names[1]:
        from dashboard.tabs.recommendations_tab import render
        render()
    elif tab == tab_names[2]:
        from dashboard.tabs.checkpoints_tab import render
        render()
    elif tab == tab_names[3]:
        from dashboard.tabs.feedback_tab import render
        render()
    elif tab == tab_names[4]:
        from dashboard.tabs.insights_tab import render
        render()


if __name__ == "__main__":
    main()
