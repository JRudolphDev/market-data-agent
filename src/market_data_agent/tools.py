"""This file holds the functions that will be called by the agent"""

from datetime import date

import pandas as pd
import yfinance as yf

from market_data_agent.models import (
    FundamentalReport,
    MomentumReport,
    Period,
    TechnicalReport,
    TickerFundamentalOutput,
    TickerMomentumOutput,
    TickerTechnicalOutput,
)

# output name -> yfinance .info key
FIELDS = {
    "market_cap": "marketCap",
    "forward_eps": "forwardEps",  # not in output, used to derive earnings_yield
    "price": "currentPrice",  # not in output, used to derive earnings_yield
    "ev_to_sales": "enterpriseToRevenue",
    "ev_to_ebitda": "enterpriseToEbitda",
    "profit_margin": "profitMargins",
    "roe": "returnOnEquity",
    "revenue_growth": "revenueGrowth",
    "debt_to_equity": "debtToEquity",  # yfinance reports as percent (150 = 1.5x)
    "free_cashflow": "freeCashflow",  # not in output, used to derive fcf_yield
}

DERIVED_INPUTS = ["forward_eps", "price", "free_cashflow"]

RSI_PERIOD = 14
ATR_PERIOD = 14
TRADING_DAYS_YEAR = 252


def get_price_history(
    tickers: list[str],
    period: Period = Period.THREE_MONTHS,
) -> pd.DataFrame:
    prices = yf.download(
        tickers,
        period=period.value,
        auto_adjust=True,
        progress=False,
    )["Close"]

    return prices.to_frame() if isinstance(prices, pd.Series) else prices


def summarize_momentum(
    tickers: list[str],
    period: Period = Period.THREE_MONTHS,
) -> MomentumReport:
    raw = get_price_history(tickers, period)

    all_blank = raw.isna().all()
    missing = list(raw.columns[all_blank])

    prices = raw.drop(columns=missing).ffill().dropna()

    if len(prices) < 3:
        raise ValueError(f"Insufficient price history. No data found for: {missing}")

    daily_returns = prices.pct_change().dropna()

    total_return = prices.iloc[-1] / prices.iloc[0] - 1
    volatility = daily_returns.std() * len(daily_returns) ** 0.5

    summary = pd.DataFrame(
        {
            "total_return": total_return,
            "period_volatility": volatility,
            "risk_adjusted_momentum": total_return / volatility,
        }
    ).sort_values("total_return", ascending=False)

    results = []
    for ticker in summary.index:
        results.append(
            TickerMomentumOutput(
                ticker=ticker,
                total_return=summary.loc[ticker, "total_return"],
                period_volatility=summary.loc[ticker, "period_volatility"],
                risk_adjusted_momentum=summary.loc[ticker, "risk_adjusted_momentum"],
            )
        )

    return MomentumReport(
        period=period,
        start_date=prices.index[0],
        end_date=prices.index[-1],
        trading_days=len(prices),
        results=results,
        missing_tickers=missing,
    )


def get_fundamentals(tickers: list[str]) -> pd.DataFrame:
    rows = {}
    for t in tickers:
        info = yf.Ticker(t).info
        if not info.get("marketCap"):
            continue
        rows[t] = {k: info.get(v) for k, v in FIELDS.items()}
        rows[t]["sector"] = info.get("sector")
    return pd.DataFrame.from_dict(rows, orient="index")


def rank_score(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Average percentile rank across cols (0 to 1, higher is better)."""
    return df[cols].rank(pct=True).mean(axis=1)


def summarize_fundamentals(tickers: list[str]) -> FundamentalReport:
    df = get_fundamentals(tickers)
    missing_tickers = [t for t in tickers if t not in df.index]

    if df.empty:
        raise ValueError(f"No fundamental data found for: {missing_tickers}")

    num = list(FIELDS)
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")

    df["debt_to_equity"] = df["debt_to_equity"] / 100

    # yields stay correctly ordered when earnings are negative, unlike P/E
    df["fcf_yield"] = df["free_cashflow"] / df["market_cap"]
    df["earnings_yield"] = df["forward_eps"] / df["price"]
    df = df.drop(columns=DERIVED_INPUTS)

    if len(df) >= 3:
        # percentile ranks within this ticker set (0 to 1, higher is better)
        df["value_score"] = rank_score(df, ["earnings_yield", "fcf_yield"])
        df["quality_score"] = rank_score(df, ["roe", "profit_margin", "revenue_growth"])
    else:
        df["value_score"] = None
        df["quality_score"] = None

    df = df.sort_values("quality_score", ascending=False)
    df = df.astype(object).where(df.notna(), None)

    results = [TickerFundamentalOutput(ticker=t, **row) for t, row in df.to_dict("index").items()]
    return FundamentalReport(as_of=date.today(), missing_tickers=missing_tickers, results=results)


def wilder(s: pd.Series, period: int) -> pd.Series:
    return s.ewm(alpha=1 / period, adjust=False).mean()


def compute_rsi(close: pd.Series) -> float:
    delta = close.diff()
    gain = wilder(delta.clip(lower=0), RSI_PERIOD)
    loss = wilder(-delta.clip(upper=0), RSI_PERIOD)
    rs = gain / loss
    return (100 - 100 / (1 + rs)).iloc[-1]


def compute_atr_pct(df: pd.DataFrame) -> float:
    prev_close = df["Close"].shift()
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return wilder(tr, ATR_PERIOD).iloc[-1] / df["Close"].iloc[-1]


def classify_trend(price: float, sma_50: float, sma_200: float) -> str:
    if price > sma_50 > sma_200:
        return "uptrend"
    if price < sma_50 < sma_200:
        return "downtrend"
    return "mixed"


def analyze_ticker(df: pd.DataFrame) -> dict:
    close = df["Close"]
    price = close.iloc[-1]

    sma_50 = close.rolling(50).mean().iloc[-1]
    sma_200 = close.rolling(200).mean().iloc[-1]

    year = df.tail(TRADING_DAYS_YEAR)
    high_52w = year["High"].max()
    low_52w = year["Low"].min()

    # recent volume vs the longer baseline, confirms whether a move has support
    volume = df["Volume"]
    relative_volume = volume.tail(20).mean() / volume.tail(TRADING_DAYS_YEAR).mean()

    return {
        "price": price,
        "rsi_14": compute_rsi(close),
        "pct_from_sma_50": price / sma_50 - 1,
        "pct_from_sma_200": price / sma_200 - 1,
        "trend": classify_trend(price, sma_50, sma_200),
        "pct_from_52w_high": price / high_52w - 1,
        "pct_from_52w_low": price / low_52w - 1,
        "atr_pct": compute_atr_pct(df),
        "relative_volume": relative_volume,
    }


def summarize_technicals(tickers: list[str]) -> TechnicalReport:
    rows = {}
    last_dates = []
    insufficient_history = []
    for t in tickers:
        # 2y so the 200 day average and 52 week range are fully populated
        df = yf.Ticker(t).history(period="2y", auto_adjust=True)
        if df.empty:
            continue
        if len(df) < 200:
            insufficient_history.append(t)
            continue
        rows[t] = analyze_ticker(df)
        last_dates.append(df.index[-1])

    missing_tickers = [t for t in tickers if t not in rows and t not in insufficient_history]

    if not rows:
        raise ValueError(
            f"No technical data. Unknown tickers: {missing_tickers}. "
            f"Fewer than 200 trading days: {insufficient_history}."
        )

    summary = pd.DataFrame.from_dict(rows, orient="index")
    summary = summary.sort_values("pct_from_52w_high", ascending=False)

    results = [
        TickerTechnicalOutput(ticker=t, **row) for t, row in summary.to_dict("index").items()
    ]
    return TechnicalReport(
        as_of=max(last_dates),
        missing_tickers=missing_tickers,
        insufficient_history=insufficient_history,
        results=results,
    )


if __name__ == "__main__":
    result = summarize_momentum(
        ["NVDA", "AVGO"],
        Period.THREE_MONTHS,
    )

    print(result.model_dump_json())
