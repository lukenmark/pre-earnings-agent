from datetime import date, datetime


def format_currency(value: float) -> str:
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:.1f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val / 1_000:.0f}K"
    return f"{sign}${abs_val:.2f}"


def format_score(score: int) -> str:
    return f"{score}/100"


def format_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def format_date(dt: date | datetime) -> str:
    return dt.strftime("%B %-d, %Y")


def days_until(dt: date) -> int:
    today = date.today()
    target = dt.date() if isinstance(dt, datetime) else dt
    return (target - today).days


def score_to_emoji(score: int) -> str:
    if score >= 70:
        return "🟢"
    if score >= 50:
        return "🟡"
    return "🔴"


def decision_to_emoji(decision: str) -> str:
    mapping = {"BUY": "🟢", "WATCH": "🟡", "NO_GO": "🔴"}
    return mapping.get(decision.upper(), "⚪")
