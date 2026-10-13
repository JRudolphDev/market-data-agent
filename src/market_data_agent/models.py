from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

Ticker = Annotated[str, StringConstraints(to_upper=True, pattern=r"^[A-Za-z.\-]{1,10}$")]
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

    tickers: list[Ticker] = Field(
        description=(
            "U.S.-listed stock symbols to analyze or compare. "
            "Use ticker symbols (e.g., NVDA, AVGO), not company names. "
            "Symbols are normalized to uppercase."
        ),
        min_length=1,
        max_length=8,
    )
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
