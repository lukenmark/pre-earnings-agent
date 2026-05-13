"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String, unique=True, nullable=False, index=True),
        sa.Column("company_name", sa.String, nullable=False),
        sa.Column("earnings_date", sa.Date, nullable=True),
        sa.Column("fiscal_year_end", sa.String, nullable=True),
        sa.Column("status", sa.String, nullable=False, server_default="candidate"),
        sa.Column("date_added", sa.DateTime, nullable=False),
        sa.Column("industry", sa.String, nullable=True),
        sa.Column("eps_ttm", sa.Float, nullable=True),
        sa.Column("market_cap", sa.Float, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String, sa.ForeignKey("watchlist.ticker"), nullable=False, index=True),
        sa.Column("checkpoint", sa.String, nullable=False),
        sa.Column("composite_score", sa.Integer, nullable=False),
        sa.Column("decision", sa.String, nullable=False),
        sa.Column("hypothesis_direction", sa.String, nullable=False),
        sa.Column("hard_veto", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("core_override_triggered", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("report_json", sa.Text, nullable=False),
        sa.Column("prior_composite_score", sa.Integer, nullable=True),
        sa.Column("score_delta", sa.Integer, nullable=True),
        sa.Column("includes_mbp", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String, nullable=False, index=True),
        sa.Column("company_name", sa.String, nullable=False),
        sa.Column("recommendation", sa.String, nullable=False),
        sa.Column("composite_score", sa.Integer, nullable=False),
        sa.Column("checkpoint_trajectory_json", sa.Text, nullable=False),
        sa.Column("thesis", sa.Text, nullable=False),
        sa.Column("earnings_date", sa.DateTime, nullable=False),
        sa.Column("alert_json", sa.Text, nullable=False),
        sa.Column("hard_veto", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("alert_sent_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String, nullable=False, index=True),
        sa.Column("user_id", sa.String, nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "industry_assessments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("industry_name", sa.String, nullable=False, index=True),
        sa.Column("composite_score", sa.Integer, nullable=False),
        sa.Column("metrics_json", sa.Text, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="active"),
        sa.Column("consecutive_low_weeks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assessed_at", sa.DateTime, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_table(
        "raw_data_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cache_key", sa.String, unique=True, nullable=False, index=True),
        sa.Column("data_type", sa.String, nullable=False),
        sa.Column("ticker", sa.String, nullable=True, index=True),
        sa.Column("content_json", sa.Text, nullable=False),
        sa.Column("fetched_at", sa.DateTime, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("raw_data_cache")
    op.drop_table("industry_assessments")
    op.drop_table("feedback")
    op.drop_table("alerts")
    op.drop_table("checkpoints")
    op.drop_table("watchlist")
