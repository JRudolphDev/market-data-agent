"""This file holds the functions that will be called by the agent"""

import pandas as pd
import yfinance as yf

from market_data_agent.models import MomentumReport, Period, TickerMomentumOutput


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
    prices = get_price_history(tickers, period).ffill().dropna()

    if len(prices) < 3:
        raise ValueError("Insufficient price history")

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
    )


if __name__ == "__main__":
    result = summarize_momentum(
        ["NVDA", "AVGO"],
        Period.THREE_MONTHS,
    )

    print(result.model_dump_json())
