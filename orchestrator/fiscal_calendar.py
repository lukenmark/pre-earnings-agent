from dataclasses import dataclass
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


@dataclass
class FiscalQuarter:
    label: str          # e.g. "FQ3 2026"
    start_date: date
    end_date: date
    calendar_year: int
    fiscal_year: int
    quarter_number: int  # 1-4


class FiscalCalendar:
    def __init__(self, ticker: str, fiscal_year_end_month: int, fiscal_year_end_day: int = 31):
        """
        fiscal_year_end_month: month number when fiscal year ends.
        Examples:
          - Standard calendar year: month=12
          - Snowflake (Jan 31): month=1
          - Salesforce (Jan 31): month=1
          - Nike (May 31): month=5
          - Apple (late September): month=9
        """
        self.ticker = ticker
        self.fy_end_month = fiscal_year_end_month
        self.fy_end_day = fiscal_year_end_day

    def get_fiscal_year_end(self, calendar_year: int) -> date:
        """Returns the fiscal year end date for a given calendar year"""
        try:
            return date(calendar_year, self.fy_end_month, self.fy_end_day)
        except ValueError:
            # Handle months with fewer days (e.g. Feb 28/29)
            import calendar
            last_day = calendar.monthrange(calendar_year, self.fy_end_month)[1]
            return date(calendar_year, self.fy_end_month, min(self.fy_end_day, last_day))

    def get_quarter_for_date(self, d: date) -> FiscalQuarter:
        """Returns the fiscal quarter that contains the given date"""
        # Find the fiscal year this date belongs to
        # A fiscal year ends at fy_end_month/fy_end_day
        # Work backwards from candidate FY ends to find the one that contains d
        for year_offset in range(-1, 3):
            fy_end = self.get_fiscal_year_end(d.year + year_offset)
            fy_start = fy_end - relativedelta(years=1) + timedelta(days=1)
            if fy_start <= d <= fy_end:
                # d is in this fiscal year — find which quarter
                quarter_length = (fy_end - fy_start).days // 4
                for q in range(1, 5):
                    q_start = fy_start + timedelta(days=quarter_length * (q - 1))
                    q_end = fy_start + timedelta(days=quarter_length * q) - timedelta(days=1)
                    if q == 4:
                        q_end = fy_end
                    if q_start <= d <= q_end:
                        fy_label = fy_end.year if self.fy_end_month != 12 else d.year
                        return FiscalQuarter(
                            label=f"FQ{q} FY{fy_label}",
                            start_date=q_start,
                            end_date=q_end,
                            calendar_year=d.year,
                            fiscal_year=fy_label,
                            quarter_number=q,
                        )
        raise ValueError(f"Could not determine fiscal quarter for {d}")

    def get_prior_quarter(self, fq: FiscalQuarter) -> FiscalQuarter:
        """Returns the fiscal quarter immediately preceding the given one"""
        # Go one day before the current quarter start
        prior_date = fq.start_date - timedelta(days=1)
        return self.get_quarter_for_date(prior_date)

    def get_quarters_until_earnings(self, earnings_date: date) -> list[FiscalQuarter]:
        """Returns the fiscal quarter containing earnings_date and the prior quarter"""
        current_fq = self.get_quarter_for_date(earnings_date)
        prior_fq = self.get_prior_quarter(current_fq)
        return [current_fq, prior_fq]

    def get_checkpoint_date(self, earnings_date: date, days_before: int) -> date:
        """Returns the date N days before earnings (for T-21, T-14, T-7, T-3)"""
        return earnings_date - timedelta(days=days_before)

    @classmethod
    def from_ticker_info(cls, ticker: str, fiscal_year_end_str: str | None) -> "FiscalCalendar":
        """
        Parse fiscal year end from string like "January 31", "September 30", "December 31".
        Falls back to calendar year (December) if unknown.
        """
        if not fiscal_year_end_str:
            return cls(ticker, 12, 31)

        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }
        parts = fiscal_year_end_str.lower().split()
        month = month_map.get(parts[0], 12)
        day = int(parts[1]) if len(parts) > 1 else 31
        return cls(ticker, month, day)
