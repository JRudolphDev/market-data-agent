# Market Data Agent

This is a Python agent that answers natural-language questions about equities
by calling tools. Claude decides which tools to call and can combine several
tools' results into one answer. The answer is structured and validated
(Pydantic), not free text. This agent uses a raw Claude API tool-calling loop,
no agent frameworks. It runs on claude-sonnet-5-5, pinned in agent.py.

Claude does no math beyond reformatting. The tools compute every metric in
pandas; Claude converts units for readability (decimals to percentages,
earnings yield to P/E), picks which numbers matter, and explains them.

Three tools are available:

- Momentum: returns and volatility over a lookback period.
- Fundamentals: valuation, profitability, growth, and leverage.
- Technicals: trend, RSI, and position relative to moving averages and the
  52-week range.

The answer contains:

- A one-sentence headline answering the question directly.
- A verdict per ticker, per criterion, where the criteria come from the
  question. A question about valuation and momentum produces two verdicts per
  ticker.
- Key points citing the specific numbers behind each verdict.
- Caveats for missing tickers, missing metrics, and anything that makes a
  number less reliable than it looks.
- The list of tools that ran, recorded by the loop rather than reported by
  Claude, so it is always accurate.

## Example

```
uv run market-agent "Of NVDA, AMD and AVGO, which has the strongest momentum over 6 months, is any of them overbought, and which is cheapest?"
```

```
AMD has the strongest 6-month momentum, none of the three is overbought, and NVDA is the cheapest on most valuation multiples.

TICKER  MOMENTUM            OVERBOUGHT          VALUATION
AMD     favored             favored             unfavored
          - 6-month return of 121.2%, with a risk-adjusted momentum of 2.3 on 53.5% volatility.
          - RSI of 46.5, and the price is 6.8% above its 50-day average, in an uptrend.
          - Priciest of the three: EV/sales 22.3x, EV/EBITDA 96.5x, earnings yield 2.8%.
NVDA    neutral             favored             favored
          - 6-month return of 11.5%, with a risk-adjusted momentum of 0.4.
          - RSI of 44.0, so not overbought, and the price is 9.1% below its 52-week high.
          - Cheapest on most measures: EV/sales 17.5x, EV/EBITDA 26.4x, earnings yield 7.2%, which is a forward P/E of roughly 14.
AVGO    unfavored           favored             neutral
          - 6-month return of -12.4%, with a risk-adjusted momentum of -0.4.
          - RSI of 42.4, and the price is 29.8% below its 52-week high.
          - Mid-range valuation: EV/sales 18.9x, EV/EBITDA 32.3x, earnings yield 5.6%, and the highest FCF yield at 1.9%.

AMD's 6-month return is far ahead of the others, though it came with the highest volatility. All three RSI readings are between 42 and 47, so none is overbought, and relative volume is below 1.0 for NVDA and AMD. NVDA is cheapest on EV/sales, EV/EBITDA and earnings yield. AVGO scores highest on the composite value score because its FCF yield is higher. AMD has the strongest momentum but is also the most expensive.

Caveats:
  - Earnings yield is based on analyst forward estimates.
  - FCF yields are low for all three, so the composite value score is less informative than the multiples.
  - Past momentum does not predict future returns.

Tools used: summarize_momentum, summarize_technicals, summarize_fundamentals
```

## Setup

You need Python 3.13 and [uv](https://docs.astral.sh/uv/), a Python package
manager. If Python 3.13 is missing, uv downloads it.

Clone the repo and install the dependencies:

```
git clone https://github.com/JRudolphDev/market-data-agent.git
cd market-data-agent
uv sync
```

The agent needs an Anthropic API key. Copy the example file to `.env`, then
put your key in it. Git ignores `.env`, so the key stays on your machine.

```
cp .env.example .env
```

```
ANTHROPIC_API_KEY=your_key_here
```

Ask a question on the command line:

```
uv run market-agent "is NVDA overbought?"
```

Run it with no question and it asks you for one:

```
uv run market-agent
```

## How the agent loop works

The loop lives in `run_agent` in `agent.py`. It is a plain `for` loop around
the Claude API, with no agent framework.

1. **Start.** `messages` holds one user message: the question.
2. **Call the API.** Each call sends the full `messages` list, the three tool
   definitions, and the answer format. A tool definition is built from its
   Pydantic input model: the docstring tells Claude when to use the tool, and
   the fields become its input schema. The answer format is the JSON schema
   of `FinalAnswer`.
3. **Check why Claude stopped.** Every reply has a stop reason, a label for
   why Claude stopped writing.
   - `tool_use`: Claude wants data. The loop appends Claude's reply to
     `messages` as is. It then runs every tool Claude asked for and appends
     all the results in one user message. Each result carries the id of the
     request it answers. Then the loop goes back to step 2.
   - `end_turn`: Claude is done. The loop validates the text against
     `FinalAnswer`, attaches the list of tools that ran, and returns.
   - Anything else: the loop raises an error.
4. **Handle tool errors.** If a tool raises an exception, the loop does not
   crash. It sends the error message back to Claude as the tool result,
   marked as an error. Claude can then retry with different input or explain
   the gap in its answer. Only tools that returned data go in the tools used
   list.
5. **Stop.** The loop ends in one of four ways: a valid answer, an answer
   that fails validation, an unexpected stop reason, or 8 rounds with no
   answer (`MAX_ITERATIONS`). The last three raise an error, and the command
   line prints a short message.

## Tools

A tool is a Python function Claude can ask the agent to run. Each tool takes
1 to 8 ticker symbols, fetches data from Yahoo Finance with yfinance, and
computes its metrics in pandas. Percentages come back as decimals, so 0.05
means 5%.

**summarize_momentum** answers "how has the price moved?"

- Inputs: tickers and a lookback period (5d, 1mo, 3mo, 6mo, 1y, 2y, 5y or ytd).
- Returns: total return, volatility over the period, and risk-adjusted
  momentum (return divided by volatility, so a higher number means more
  return for each unit of volatility).

**summarize_fundamentals** answers "how cheap and how healthy is the company?"

- Inputs: tickers.
- Returns: market cap, earnings yield (forward earnings per share divided by
  price), EV/sales and EV/EBITDA (company value divided by sales or by
  operating profit), profit margin, return on equity, revenue growth, debt to
  equity and free cash flow yield. With 3 or more tickers it also returns a
  value score and a quality score from 0 to 1, ranked within the tickers
  asked about.

**summarize_technicals** answers "where is the price compared to its own
history?"

- Inputs: tickers.
- Returns: price, 14-day RSI (a 0 to 100 gauge where above 70 usually means
  overbought), distance from the 50-day and 200-day moving averages, a trend
  label (uptrend, downtrend or mixed), distance from the 52-week high and low,
  ATR as a share of price (average daily price range), and relative volume
  (recent trading volume compared to the past year).

## Design decisions

### Report wrapper instead of a flat list

- **Choice:** Each tool returns one report. The period, date and missing
  tickers sit on the report once, with a list of ticker rows inside.
- **Alternative:** A flat list where every ticker row carries its own copy.
- **Why:** Every ticker in a report is measured over the same window, so
  rows can't mix date ranges. It also keeps repeated keys out of the output.

### Yields instead of P/E for ranking

- **Choice:** The value score ranks earnings yield (earnings divided by
  price), not P/E (price divided by earnings).
- **Alternative:** P/E, the number most people know.
- **Why:** A company losing money has a negative P/E, say -5. Sorting by P/E
  puts it first, as if it were the cheapest stock. Its earnings yield of
  -0.20 sorts last, which is correct. For profitable companies the two are
  the same number flipped. P/E is not returned at all. Claude flips the
  yield when someone asks for a P/E.

### Verdicts attached to criteria, not tickers

- **Choice:** Each ticker holds one verdict per criterion in the question.
- **Alternative:** One verdict per ticker.
- **Why:** With one verdict, a stock that wins on momentum and loses on
  valuation becomes "neutral". That is the same label as a stock where
  nothing stands out. With one verdict per criterion, a descriptive question
  gives zero verdicts, a simple comparison gives one, and "better momentum
  and cheaper" gives two.

### Claude picks the numbers, the tools calculate them

- **Choice:** Every metric is computed in pandas and returned as a typed
  model. The answer schema tells Claude to cite only numbers that appear in
  a tool result.
- **Alternative:** Let Claude work out the numbers from raw prices.
- **Why:** Math done by the model can be wrong without looking wrong, and
  there is no way to check it. This way every number in the answer traces
  back to the tool call that produced it.

### The loop records which tools ran, not Claude

- **Choice:** The code collects each tool name as the tool runs and attaches
  the list after the answer comes back.
- **Alternative:** Ask Claude to report which tools it called.
- **Why:** The code already knows. Asking Claude costs output tokens and
  gives it a chance to misremember.

## Project structure

```
src/market_data_agent/
  agent.py    the agent loop and the tool registry
  tools.py    the three tools: yfinance data and pandas calculations
  models.py   Pydantic models for tool inputs, tool outputs and the answer
  cli.py      reads the question, handles errors and prints the table
tests/
  sample_response.json   a saved answer for testing the output format
```

## Limitations and next steps

Limitations:

- **No memory between questions.** Each run starts fresh. A follow-up like
  "what about AMD?" has no earlier question to refer to.
- **Data quality depends on yfinance.** yfinance is an unofficial library
  that reads Yahoo Finance. Fields can be missing or out of date. Missing
  metrics come back empty, and Claude lists them in the caveats.
- **Scores are relative.** The value and quality scores rank stocks against
  the other tickers in the same question, not the whole market. They need at
  least 3 tickers.
- **U.S. stocks only.** The tools expect U.S. ticker symbols. Technicals also
  need at least 200 trading days of history.
- **Not investment advice.** This is a learning project. The output describes
  past data and does not predict returns.

Next steps:

- Cache the tool definitions with prompt caching. They are about 3,800
  tokens and get sent on every call in the loop, so a three-call question
  sends them three times.
- Stream the answer as Claude writes it, instead of waiting for the full
  reply.
- Keep conversation memory, so follow-up questions work.
