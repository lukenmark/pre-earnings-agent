import streamlit as st
import json
import plotly.graph_objects as go


@st.cache_data(ttl=60)
def load_alerts():
    from storage.database import get_db
    from storage.repositories.alert_repo import get_active_buys
    alerts = []
    with get_db() as db:
        rows = get_active_buys(db)
        for row in rows:
            alert_data = {}
            if row.alert_json:
                try:
                    alert_data = json.loads(row.alert_json)
                except Exception:
                    pass
            alerts.append({
                "ticker": row.ticker,
                "company_name": row.company_name,
                "recommendation": row.recommendation,
                "composite_score": row.composite_score,
                "earnings_date": row.earnings_date,
                "hard_veto": row.hard_veto,
                "alert_sent_at": row.alert_sent_at,
                "thesis": alert_data.get("thesis", "—"),
                "core_news_score": alert_data.get("core_news_score", 0),
                "core_pag_score": alert_data.get("core_pag_score", 0),
                "insider_summary": alert_data.get("insider_summary", "—"),
                "options_snapshot": alert_data.get("options_snapshot", "—"),
                "share_structure_summary": alert_data.get("share_structure_summary", "—"),
                "checkpoint_trajectory": alert_data.get("checkpoint_trajectory", []),
            })
    return alerts


def _trajectory_sparkline(trajectory: list, ticker: str):
    if len(trajectory) < 2:
        return
    fig = go.Figure(go.Scatter(
        x=["T-21", "T-14", "T-7", "T-3"][:len(trajectory)],
        y=trajectory,
        mode="lines+markers",
        line=dict(color="#28a745", width=2),
        marker=dict(size=6),
        fill="tozeroy",
        fillcolor="rgba(40,167,69,0.1)",
    ))
    fig.update_layout(
        height=120, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color="#aaa"),
        yaxis=dict(showgrid=True, gridcolor="#333", range=[0, 100], color="#aaa"),
        showlegend=False,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="#28a745", opacity=0.5,
                  annotation_text="BUY threshold", annotation_position="right")
    st.plotly_chart(fig, use_container_width=True, key=f"sparkline_{ticker}")


def render():
    st.title("🟢 Recommendations")

    alerts = load_alerts()
    buy_alerts = [a for a in alerts if a["recommendation"] == "BUY" and not a["hard_veto"]]

    if not buy_alerts:
        st.info("No active BUY alerts. Alerts appear here after the T-3 checkpoint qualifies a ticker.")
        return

    st.success(f"**{len(buy_alerts)} active BUY alert{'s' if len(buy_alerts) != 1 else ''}**")

    for alert in buy_alerts:
        score = alert["composite_score"]
        earnings_str = str(alert["earnings_date"])[:10] if alert["earnings_date"] else "TBD"

        with st.expander(f"🟢 **{alert['ticker']}** — {alert['company_name']} | Score: {score}/100 | Earnings: {earnings_str}", expanded=True):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Thesis:**\n> {alert['thesis']}")
                st.markdown("---")
                st.markdown("**Core Scores (Directional Thesis):**")
                c1, c2 = st.columns(2)
                c1.metric("📰 News Quality", f"{alert['core_news_score']}/100")
                c2.metric("💰 Price Absorption Gap", f"{alert['core_pag_score']}/100")

                st.markdown("---")
                st.markdown("**Supporting Details:**")
                st.markdown(f"*Insider Activity:* {alert['insider_summary'][:200]}")
                st.markdown(f"*Options Flow:* {alert['options_snapshot'][:200]}")
                st.markdown(f"*Share Structure:* {alert['share_structure_summary'][:200]}")

            with col2:
                st.markdown("**Score Trajectory:**")
                if alert["checkpoint_trajectory"]:
                    _trajectory_sparkline(alert["checkpoint_trajectory"], alert["ticker"])
                    traj_str = " → ".join(str(s) for s in alert["checkpoint_trajectory"])
                    st.caption(f"T-21 → T-3: {traj_str}")
                else:
                    st.caption("No trajectory data")

                st.markdown("---")
                st.markdown(f"**Composite:** `{score}/100`")
                st.markdown(f"**Sent:** {str(alert['alert_sent_at'])[:16] if alert['alert_sent_at'] else '—'}")
                st.markdown("⚠️ *Agent does not execute trades. Human confirmation required.*")
