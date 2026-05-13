import streamlit as st
import json
import plotly.graph_objects as go
from datetime import datetime


@st.cache_data(ttl=60)
def load_all_checkpoints():
    from storage.database import get_db
    from storage.repositories.checkpoint_repo import get_by_ticker
    from storage.tables import CheckpointRow
    from sqlalchemy import distinct
    all_data = {}
    with get_db() as db:
        tickers = [r[0] for r in db.query(distinct(CheckpointRow.ticker)).all()]
        for ticker in tickers:
            cps = get_by_ticker(db, ticker)
            all_data[ticker] = []
            for cp in cps:
                report_data = {}
                if cp.report_json:
                    try:
                        report_data = json.loads(cp.report_json)
                    except Exception:
                        pass
                all_data[ticker].append({
                    "ticker": cp.ticker,
                    "checkpoint": cp.checkpoint,
                    "composite_score": cp.composite_score,
                    "decision": cp.decision,
                    "hypothesis_direction": cp.hypothesis_direction,
                    "hard_veto": cp.hard_veto,
                    "core_override": cp.core_override_triggered,
                    "flags": report_data.get("flags", []),
                    "key_findings": report_data.get("key_findings", []),
                    "factor_scores": report_data.get("factor_scores", {}),
                    "score_delta": cp.score_delta,
                    "created_at": cp.created_at,
                    "includes_mbp": cp.includes_mbp,
                })
    return all_data


def _score_trajectory_chart(checkpoints: list, ticker: str):
    cp_order = {"T-21": 0, "T-14": 1, "T-7": 2, "T-3": 3}
    sorted_cps = sorted(checkpoints, key=lambda c: cp_order.get(c["checkpoint"], 99))

    if len(sorted_cps) < 1:
        return

    labels = [c["checkpoint"] for c in sorted_cps]
    scores = [c["composite_score"] for c in sorted_cps]
    colors = ["#28a745" if s >= 70 else ("#ffc107" if s >= 50 else "#dc3545") for s in scores]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=scores,
        mode="lines+markers+text",
        text=[str(s) for s in scores],
        textposition="top center",
        line=dict(color="#4dabf7", width=2),
        marker=dict(size=10, color=colors, line=dict(width=2, color="#fff")),
    ))
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(40,167,69,0.08)", line_width=0)
    fig.add_hrect(y0=50, y1=70, fillcolor="rgba(255,193,7,0.08)", line_width=0)
    fig.add_hrect(y0=0, y1=50, fillcolor="rgba(220,53,69,0.08)", line_width=0)
    fig.add_hline(y=70, line_dash="dot", line_color="#28a745", opacity=0.6,
                  annotation_text="BUY", annotation_position="right")
    fig.add_hline(y=50, line_dash="dot", line_color="#ffc107", opacity=0.6,
                  annotation_text="WATCH", annotation_position="right")
    fig.update_layout(
        title=f"{ticker} — Score Trajectory",
        height=280, margin=dict(l=20, r=60, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(color="#aaa", showgrid=False),
        yaxis=dict(color="#aaa", gridcolor="#333", range=[0, 105]),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"traj_{ticker}")


def _factor_bar_chart(factor_scores: dict, ticker: str, checkpoint: str):
    if not factor_scores:
        return

    names, scores, colors = [], [], []
    for name, fs_data in sorted(
        factor_scores.items(),
        key=lambda x: x[1].get("score", 0) if isinstance(x[1], dict) else 0,
        reverse=True,
    ):
        score = fs_data.get("score", 0) if isinstance(fs_data, dict) else 0
        names.append(name.replace("_", " ").title())
        scores.append(score)
        colors.append("#28a745" if score >= 70 else ("#ffc107" if score >= 50 else "#dc3545"))

    fig = go.Figure(go.Bar(
        x=scores, y=names, orientation="h",
        marker_color=colors,
        text=[f"{s}/100" for s in scores],
        textposition="outside",
    ))
    fig.update_layout(
        height=max(250, len(names) * 35),
        margin=dict(l=0, r=60, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 115], color="#aaa", showgrid=True, gridcolor="#333"),
        yaxis=dict(color="#aaa"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"factors_{ticker}_{checkpoint}")


def render():
    st.title("📊 Checkpoint Reports")

    all_data = load_all_checkpoints()

    if not all_data:
        st.info("No checkpoint data yet. Run `/analyze TICKER` in Telegram to start.")
        return

    # Search and select
    col1, col2 = st.columns([2, 1])
    with col1:
        tickers = sorted(all_data.keys())
        selected = st.selectbox("Select Ticker", tickers)
    with col2:
        cp_select = "All"
        if selected:
            cp_labels = [c["checkpoint"] for c in all_data.get(selected, [])]
            cp_select = st.selectbox("Checkpoint", ["All"] + sorted(set(cp_labels)))

    if not selected:
        return

    checkpoints = all_data[selected]

    # Score trajectory chart (always shown at top)
    if len(checkpoints) >= 2:
        _score_trajectory_chart(checkpoints, selected)

    # Filter by checkpoint if selected
    if cp_select != "All":
        checkpoints = [c for c in checkpoints if c["checkpoint"] == cp_select]

    # Render each checkpoint report
    for cp in sorted(checkpoints, key=lambda c: c["created_at"] or datetime.min, reverse=True):
        decision_icon = "🟢" if cp["decision"] == "BUY" else ("🟡" if cp["decision"] == "WATCH" else "🔴")
        veto_text = " 🚫 HARD VETO" if cp["hard_veto"] else ""
        override_text = " ⚡ CORE OVERRIDE" if cp["core_override"] else ""
        delta_text = f" ({cp['score_delta']:+d})" if cp.get("score_delta") else ""

        with st.expander(
            f"{decision_icon} {cp['checkpoint']} — Score: {cp['composite_score']}/100{delta_text}{veto_text}{override_text}",
            expanded=(cp_select != "All"),
        ):
            col1, col2 = st.columns([1, 1])

            with col1:
                st.markdown(f"**Decision:** {cp['decision']} | **Hypothesis:** {cp['hypothesis_direction']}")
                if cp["flags"]:
                    for f in cp["flags"]:
                        st.warning(f)
                if cp["key_findings"]:
                    st.markdown("**Key Findings:**")
                    for f in cp["key_findings"]:
                        st.markdown(f"• {f}")
                if cp.get("includes_mbp"):
                    st.info("📋 MBP included in this checkpoint (T-21)")

            with col2:
                if cp["factor_scores"]:
                    st.markdown("**Factor Scores:**")
                    _factor_bar_chart(cp["factor_scores"], cp["ticker"], cp["checkpoint"])
