import streamlit as st
import json
import plotly.graph_objects as go
from collections import defaultdict
from datetime import datetime


@st.cache_data(ttl=60)
def load_insights_data():
    from storage.database import get_db
    from storage.tables import CheckpointRow
    from storage.repositories.industry_repo import get_active

    checkpoints = []
    industry_data = []

    with get_db() as db:
        rows = db.query(CheckpointRow).all()
        for row in rows:
            factor_scores = {}
            if row.report_json:
                try:
                    data = json.loads(row.report_json)
                    factor_scores = data.get("factor_scores", {})
                except Exception:
                    pass
            checkpoints.append({
                "ticker": row.ticker,
                "checkpoint": row.checkpoint,
                "composite_score": row.composite_score,
                "decision": row.decision,
                "hard_veto": row.hard_veto,
                "core_override": row.core_override_triggered,
                "created_at": row.created_at,
                "factor_scores": factor_scores,
            })

        ind_rows = get_active(db)
        for row in ind_rows:
            metrics = {}
            if row.metrics_json:
                try:
                    metrics = json.loads(row.metrics_json)
                except Exception:
                    pass
            industry_data.append({
                "industry_name": row.industry_name,
                "composite_score": row.composite_score,
                "status": row.status,
                "assessed_at": row.assessed_at,
                "metrics": metrics,
            })

    return checkpoints, industry_data


def render():
    st.title("🧠 Strategy Insights")

    checkpoints, industry_data = load_insights_data()

    if not checkpoints:
        st.info("No data yet. Run analysis on some tickers to see insights.")
        return

    # ── Score Distribution ─────────────────────────────────────
    st.subheader("📊 Composite Score Distribution")

    scores = [c["composite_score"] for c in checkpoints]
    decisions = [c["decision"] for c in checkpoints]

    col1, col2 = st.columns([2, 1])
    with col1:
        fig = go.Figure()
        for decision, color in [("BUY", "#28a745"), ("WATCH", "#ffc107"), ("NO_GO", "#dc3545")]:
            dec_scores = [s for s, d in zip(scores, decisions) if d == decision]
            if dec_scores:
                fig.add_trace(go.Histogram(
                    x=dec_scores, name=decision,
                    marker_color=color, opacity=0.75,
                    xbins=dict(start=0, end=100, size=5),
                ))
        fig.update_layout(
            barmode="overlay",
            height=300, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title="Composite Score", color="#aaa", gridcolor="#333"),
            yaxis=dict(title="Count", color="#aaa", gridcolor="#333"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#aaa")),
        )
        st.plotly_chart(fig, use_container_width=True, key="score_dist")

    with col2:
        total = len(checkpoints)
        buy_pct = sum(1 for d in decisions if d == "BUY") / max(total, 1) * 100
        watch_pct = sum(1 for d in decisions if d == "WATCH") / max(total, 1) * 100
        no_go_pct = sum(1 for d in decisions if d == "NO_GO") / max(total, 1) * 100
        veto_count = sum(1 for c in checkpoints if c["hard_veto"])
        override_count = sum(1 for c in checkpoints if c["core_override"])

        st.metric("Total Checkpoints", total)
        st.metric("🟢 BUY Rate", f"{buy_pct:.0f}%")
        st.metric("🟡 WATCH Rate", f"{watch_pct:.0f}%")
        st.metric("🔴 NO-GO Rate", f"{no_go_pct:.0f}%")
        if veto_count:
            st.metric("🚫 Hard Vetos", veto_count)
        if override_count:
            st.metric("⚡ Core Overrides", override_count)

    st.markdown("---")

    # ── Factor Score Patterns ──────────────────────────────────
    st.subheader("🔬 Average Factor Scores by Decision")

    factor_by_decision = defaultdict(lambda: defaultdict(list))
    for cp in checkpoints:
        for fname, fs_data in cp["factor_scores"].items():
            score = fs_data.get("score", 0) if isinstance(fs_data, dict) else 0
            factor_by_decision[cp["decision"]][fname].append(score)

    if factor_by_decision:
        factor_names = set()
        for d in factor_by_decision.values():
            factor_names.update(d.keys())
        factor_names = sorted(factor_names)

        fig = go.Figure()
        for decision, color in [("BUY", "#28a745"), ("WATCH", "#ffc107"), ("NO_GO", "#dc3545")]:
            if decision not in factor_by_decision:
                continue
            avgs = [
                sum(factor_by_decision[decision].get(f, [0])) / max(len(factor_by_decision[decision].get(f, [1])), 1)
                for f in factor_names
            ]
            fig.add_trace(go.Bar(
                name=decision,
                x=[f.replace("_", " ").title() for f in factor_names],
                y=avgs,
                marker_color=color,
                opacity=0.85,
            ))

        fig.update_layout(
            barmode="group", height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(color="#aaa", tickangle=-30),
            yaxis=dict(color="#aaa", gridcolor="#333", range=[0, 100]),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#aaa")),
        )
        st.plotly_chart(fig, use_container_width=True, key="factor_patterns")

    st.markdown("---")

    # ── Industry Trends ────────────────────────────────────────
    st.subheader("🏭 Industry Scores")

    if industry_data:
        ind_names = [i["industry_name"] for i in industry_data]
        ind_scores = [i["composite_score"] for i in industry_data]
        ind_colors = ["#28a745" if s >= 60 else ("#ffc107" if s >= 40 else "#dc3545") for s in ind_scores]

        fig = go.Figure(go.Bar(
            x=ind_scores, y=ind_names, orientation="h",
            marker_color=ind_colors,
            text=[f"{s}/100" for s in ind_scores],
            textposition="outside",
        ))
        fig.update_layout(
            height=max(200, len(ind_names) * 40),
            margin=dict(l=0, r=60, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(range=[0, 115], color="#aaa", gridcolor="#333"),
            yaxis=dict(color="#aaa"),
        )
        st.plotly_chart(fig, use_container_width=True, key="industry_scores")
    else:
        st.info("No industry assessments yet. Run `orch.run_industry_assessment('Technology')` to populate.")

    st.markdown("---")

    # ── Ticker Score Over Time ─────────────────────────────────
    st.subheader("📈 Score Over Time by Ticker")

    all_tickers = sorted({c["ticker"] for c in checkpoints})
    selected_ticker = st.selectbox("Select ticker", all_tickers, key="insights_ticker") if all_tickers else None

    if selected_ticker:
        ticker_cps = [c for c in checkpoints if c["ticker"] == selected_ticker]
        ticker_cps.sort(key=lambda c: c["created_at"] or datetime.min)

        if ticker_cps:
            fig = go.Figure(go.Scatter(
                x=[c["checkpoint"] for c in ticker_cps],
                y=[c["composite_score"] for c in ticker_cps],
                mode="lines+markers+text",
                text=[c["decision"] for c in ticker_cps],
                textposition="top center",
                marker=dict(
                    size=10,
                    color=["#28a745" if c["decision"] == "BUY" else
                           ("#ffc107" if c["decision"] == "WATCH" else "#dc3545")
                           for c in ticker_cps],
                ),
                line=dict(color="#4dabf7", width=2),
            ))
            fig.add_hline(y=70, line_dash="dot", line_color="#28a745", opacity=0.5)
            fig.add_hline(y=50, line_dash="dot", line_color="#ffc107", opacity=0.5)
            fig.update_layout(
                height=280, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(color="#aaa"),
                yaxis=dict(color="#aaa", gridcolor="#333", range=[0, 105]),
            )
            st.plotly_chart(fig, use_container_width=True, key=f"timeline_{selected_ticker}")
