from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

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


class Trend(StrEnum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    MIXED = "mixed"


class Verdict(StrEnum):
    """How a ticker comes out on the criterion the user asked about.

    Not a buy rating. The direction is set by the question: for "which is
    cheaper", FAVORED means cheaper; for "is it overbought", FAVORED means not
    overbought. FAVORED is always the good end of whatever was asked.

    One Verdict per criterion the question asks about. See TickerScan.verdicts.
    """

    FAVORED = "favored"
    NEUTRAL = "neutral"
    UNFAVORED = "unfavored"
    INSUFFICIENT_DATA = "insufficient_data"


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


class TickerTechnicalInput(BaseModel):
    """
    Analyze price trend and chart position for one or more U.S.-listed stocks.

    Use this tool when asked where a stock is trading relative to its own
    history, whether it is overbought or oversold, how far it has fallen from
    its highs, or whether it is above or below its moving averages. Do not use
    it to measure returns or compare performance, which the momentum tool
    covers.

    Reports the following metrics from the last two years of daily adjusted
    OHLCV data:
    - price: Most recent closing price in USD.
    - rsi_14: Relative strength index over 14 days, from 0 to 100. Above 70 is
      conventionally overbought, below 30 oversold.
    - pct_from_sma_50: Price relative to its 50 day simple moving average.
    - pct_from_sma_200: Price relative to its 200 day simple moving average.
    - trend: One of uptrend, downtrend, or mixed. uptrend means price is above
      the 50 day average and the 50 day is above the 200 day. downtrend is the
      reverse. mixed means the two averages disagree, which includes recent
      crossovers in either direction.
    - pct_from_52w_high: Drawdown from the highest intraday price of the last
      52 weeks. Always zero or negative.
    - pct_from_52w_low: Gain above the lowest intraday price of the last 52
      weeks. Always zero or positive.
    - atr_pct: Average true range over 14 days divided by price. A measure of
      typical daily range that accounts for overnight gaps.
    - relative_volume: Average volume over the last 20 days divided by average
      volume over the last 52 weeks.

    Output details:
    - Percentages and ratios are decimals (e.g., -0.0524 represents a 5.24%
      decline). rsi_14 is a 0 to 100 index, not a decimal.
    - relative_volume above 1.0 means recent trading is heavier than the yearly
      baseline, which suggests a price move has participation behind it. Below
      1.0 suggests a move is happening on thin volume.
    - atr_pct is a volatility measure, not a directional signal. Use it to size
      stops or to compare how much two stocks typically move in a day.
    - Lookback windows are fixed at the conventional 14, 50, and 200 days and
      52 weeks. They are not configurable.
    - Results are ranked by pct_from_52w_high, closest to the high first.
    - as_of reports the date of the most recent close used.
    - Tickers with fewer than 200 trading days of history, including recent
      IPOs, cannot produce a 200 day average and are reported in
      `insufficient_history` without failing the entire request.
    - Unknown or unavailable ticker symbols are reported in `missing_tickers`
      without failing the entire request. Tell the user the stock is too new
      for these indicators, not that it doesn't exist.
    - Valid ticker results are returned even when some symbols are missing.

    These indicators describe where price has been, not where it is going.
    Evidence that they predict future returns is weak, so treat them as context
    alongside fundamentals and momentum rather than as standalone signals. An
    extreme rsi_14 reading can persist for weeks in a strong trend and is not
    on its own a reason to expect a reversal.
    """

    tickers: Tickers


class TickerTechnicalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker
    price: Rounded4 | None
    rsi_14: Rounded4 | None
    pct_from_sma_50: Rounded4 | None
    pct_from_sma_200: Rounded4 | None
    trend: Trend | None
    pct_from_52w_high: Rounded4 | None
    pct_from_52w_low: Rounded4 | None
    atr_pct: Rounded4 | None
    relative_volume: Rounded4 | None


class TechnicalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: date
    results: list[TickerTechnicalOutput]
    missing_tickers: list[str] = []
    insufficient_history: list[str] = []


class TickerScan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: Ticker
    verdicts: list[Verdict]
    key_points: list[str]


class FinalAnswer(BaseModel):
    """
    The structured answer to a market data question.

    Fill this in from the tool results. Do not compute new numbers; every
    figure cited must appear in a tool result, copied exactly.

    - headline: One sentence answering the question that was asked. State the
      conclusion, not what was analyzed. Write "NVDA is the stronger performer
      over three months", not "I compared NVDA and AMD".
    - criteria: The dimensions the question asks you to judge, in short
      consistent names such as "momentum", "valuation", or "overbought".
      Empty for purely descriptive questions that have no better or worse
      answer, such as "what is NVDA's RSI".
    - verdicts (in each scan row): One Verdict per criterion, in the same
      order as criteria. favored is the good end of what was asked.
    - key_points (in each scan row): One to three short points, citing the
      numbers that drove the verdicts.
    - scan: One entry for every ticker the user asked about, including tickers
      that returned no data. Order rows from most to least favored on the
      first criterion, or keep the user's order when there are no criteria.
      For a ticker with no data from any tool, set every verdict to
      insufficient_data and use key_points to say why (for example, unknown
      symbol or too little trading history). Never drop a requested ticker.
    - detail: Free-form reasoning, two to four sentences. Explain why the
      verdicts came out as they did. When a ticker is favored on one criterion
      and unfavored on another, say so here rather than letting the split pass
      without comment. Leave empty when the headline and key points already
      cover it.
    - caveats: One short sentence per limitation. Use for metrics that are null
      or negative, and any case where a number is less reliable than it looks.
      Leave empty when there are none; do not invent filler.
    """

    model_config = ConfigDict(extra="forbid")

    headline: str
    criteria: list[str]
    scan: list[TickerScan]
    detail: str
    caveats: list[str]

    @model_validator(mode="after")
    def verdicts_match_criteria(self):
        for row in self.scan:
            if len(row.verdicts) != len(self.criteria):
                raise ValueError(
                    f"{row.ticker} has {len(row.verdicts)} verdicts "
                    f"but there are {len(self.criteria)} criteria"
                )
        return self


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: FinalAnswer
    tools_used: list[str]


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
