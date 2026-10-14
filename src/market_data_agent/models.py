from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

Ticker = Annotated[str, StringConstraints(to_upper=True, pattern=r"^[A-Za-z.\-]{1,10}$")]
Tickers = Annotated[
    list[Ticker],
    Field(
        description=(
            "U.S.-listed stock symbols to analyze or compare. "
            "Use ticker symbols (e.g., NVDA, AVGO), not company names. "
            "Symbols are normalized to uppercase."
        ),
        min_length=1,
        max_length=8,
    ),
]
Rounded4 = Annotated[float, AfterValidator(lambda v: round(v, 4))]


class Period(StrEnum):
    """Supported historical market-data lookback periods."""

    ONE_WEEK = "5d"
    ONE_MONTH = "1mo"
    THREE_MONTHS = "3mo"
    SIX_MONTHS = "6mo"
    ONE_YEAR = "1y"
    TWO_YEARS = "2y"
    FIVE_YEARS = "5y"
    YEAR_TO_DATE = "ytd"


class TickerMomentumInput(BaseModel):
    """
    Analyze and compare historical price momentum for one or more U.S.-listed stocks.

    Use this tool when asked to evaluate stock performance, compare momentum,
    identify stronger performers, or assess returns relative to volatility.

    Calculates the following metrics using adjusted daily closing prices:
    - total_return: Cumulative return over the selected period.
    - period_volatility: Daily return volatility scaled to the analysis period.
    - risk_adjusted_momentum: Total return divided by period volatility.
    Higher values indicate stronger returns relative to volatility.

    Output details:
    - Returns and volatility are decimals rounded to 4 decimal places
    (e.g., 0.0524 represents 5.24%).
    - Risk-adjusted momentum is a unitless ratio, not a percentage.
    - Results are ranked by total return, highest first.
    - All tickers are evaluated over the same common window. start_date,
    end_date, and trading_days report the actual window used, which may be
    shorter than requested if a ticker has limited history.
    - Unknown or unavailable ticker symbols are reported in `missing_tickers`
    without failing the entire request.
    - Valid ticker results are returned even when some symbols are missing.

    Use total_return as the primary measure of price momentum and
    risk_adjusted_momentum to evaluate performance relative to volatility.
    Historical momentum does not predict future returns.
    """

    tickers: Tickers
    period: Period = Field(
        description=(
            "Historical lookback window for calculating momentum metrics. "
            "Use the same period for all tickers to ensure comparability."
        ),
    )


class TickerMomentumOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker
    total_return: Rounded4
    period_volatility: Rounded4
    risk_adjusted_momentum: Rounded4


class MomentumReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: Period
    start_date: date
    end_date: date
    trading_days: int
    results: list[TickerMomentumOutput]
    missing_tickers: list[str] = []


class TickerFundamentalInput(BaseModel):
    """
    Analyze and compare company fundamentals for one or more U.S.-listed stocks.

    Use this tool when asked to evaluate valuation, profitability, growth, or
    balance sheet strength, to compare company quality, or to identify cheap or
    expensive stocks. Do not use it for price performance questions.

    Reports the following metrics from the most recent available filings and
    current market prices:
    - sector: Needed to interpret every valuation multiple below.
    - market_cap: Company size in USD.
    - earnings_yield: Forward earnings per share divided by price, the inverse
      of forward P/E. An earnings_yield of 0.05 equals a forward P/E of 20.
      Negative when the company is expected to lose money.
    - ev_to_sales: Enterprise value to revenue. The primary valuation multiple
      for unprofitable companies, since it stays meaningful when earnings and
      EBITDA are negative.
    - ev_to_ebitda: Enterprise value to EBITDA, neutral to capital structure.
      Null or negative for unprofitable companies, where it is not meaningful.
    - fcf_yield: Free cash flow divided by market cap.
    - roe: Return on equity.
    - profit_margin: Net income divided by revenue.
    - revenue_growth: Year over year revenue growth.
    - debt_to_equity: Leverage.
    - value_score, quality_score: Composite rankings.

    Output details:
    - Margins, yields, growth, and roe are decimals (e.g., 0.0524 represents 5.24%).
    - ev_to_sales, ev_to_ebitda, and debt_to_equity are multiples (e.g., 25.3 means 25.3x).
    - market_cap is an absolute USD amount.
    - value_score and quality_score are composite percentile ranks from 0 to 1,
      where higher is better:
      - value_score ranks earnings_yield and fcf_yield.
      - quality_score ranks roe, profit_margin, and revenue_growth.
      - They are relative to the tickers in this request only, not absolute
        grades, and are most useful within a single sector.
      - Each score averages the available metrics; missing metrics are skipped,
        not treated as zero.
      - Both are null when fewer than three tickers return data. Compare the
        underlying metrics directly instead.
    - Any individual metric may be null when a company does not report it.
    - For unprofitable companies, earnings_yield, fcf_yield, and therefore
      value_score are negative or unreliable. Use ev_to_sales and
      revenue_growth to compare them, and treat value_score as a ranking of who
      burns cash slowest rather than as a measure of cheapness.
    - Forward P/E is not returned directly. Invert earnings_yield when a user
      asks for a P/E, and note that it is based on analyst estimates.
    - Results are ranked by quality_score, highest first.
    - Unknown or unavailable ticker symbols are reported in `missing_tickers`
      without failing the entire request.
    - Valid ticker results are returned even when some symbols are missing.

    Fundamentals update only on reporting dates and lag the current price.
    Compare valuation multiples within a sector, not across sectors.
    """

    tickers: Tickers


class TickerFundamentalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker
    sector: str | None
    market_cap: float | None
    earnings_yield: Rounded4 | None
    ev_to_sales: Rounded4 | None
    ev_to_ebitda: Rounded4 | None
    profit_margin: Rounded4 | None
    roe: Rounded4 | None
    revenue_growth: Rounded4 | None
    debt_to_equity: Rounded4 | None
    fcf_yield: Rounded4 | None
    value_score: Rounded4 | None
    quality_score: Rounded4 | None


class FundamentalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: date
    results: list[TickerFundamentalOutput]
    missing_tickers: list[str] = []


if __name__ == "__main__":
    nvda = TickerMomentumOutput(
        ticker="NVDA",
        total_return=0.127778,
        period_volatility=0.185403,
        risk_adjusted_momentum=0.689187,
    )
    avgo = TickerMomentumOutput(
        ticker="AVGO",
        total_return=-0.056898,
        period_volatility=0.191283,
        risk_adjusted_momentum=-0.297454,
    )

    start_date = date(2026, 7, 13)
    end_date = date(2026, 10, 12)

    report = MomentumReport(
        period=Period.THREE_MONTHS,
        start_date=start_date,
        end_date=end_date,
        trading_days=65,
        results=[nvda, avgo],
    )
    print(report.model_dump_json())
