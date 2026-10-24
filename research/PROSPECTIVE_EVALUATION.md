# Prospective effectiveness measurement (research-only)

This evaluator is for *future* analyst-approved, prospectively recorded
candidate ideas. It is not a trading engine, signal generator, price
provider or proof of predictive alpha. In particular, neither a SEC filing
nor a research queue item is an approved investment signal.

## Current status

The example ledger deliberately has ZERO signals because no immutable,
timestamped, pre-declared stock picks with their first-public evidence
timestamps and prices have been established in the available repository.
Thus the genuine market-performance metric is **N/A**, not zero percent.

For reproducible test-only validation:

    python -m pearl_hunter_quant.forward_eval --signals examples/forward_signals_synthetic.json --prices examples/forward_prices_synthetic.json --as-of-utc 2026-10-24T23:59:59Z --output local_results/forward_eval.json

This command makes NO network calls. All example data are synthetic.

## Recording an actual research candidate

An authorized analyst must commit the candidate to a durable *private*
append-only ledger BEFORE the future price move. Record:
- Unique signal_id, ticker and decision=analyst_candidate.
- recorded_at_utc in ISO format with timezone (the actual recording time).
- source_public_at_utc, independently verifiable publication date-time of
  supporting primary evidence and not later than the recorded timestamp.
- One or more HTTPS primary source URLs and a dated thesis/risk discussion.

A timestamp typed into a historical JSON file is **not** proof of when it
was recorded. Use Git signed commits, server ingestion timestamps and
append-only event storage with clear change history.

## Adjusted market price evidence

Supply JSON schema_version=1, price_type=adjusted_close, a documented
source, and prices with ticker/date/adjusted_close. Benchmark defaults to
SPY. Validate the provider's adjustment methodology, dividends, splits,
ticker changes, missing observations and delistings separately. All
sensitive work stays local/private.

The entry convention is the first SPY benchmark trading session **after**
the signal date, using adjusted *closing* prices. The exit is 5, 20 or 60
benchmark sessions later. This is a *research return convention*, not an
executable fill; fees are a configurable round-trip basis-point deduction.

If a stock observation is missing on the entry or exit benchmark session,
the evaluator reports missing_price instead of sliding the trade to another
day. An insufficient future window produces immature, not a fabricated
return. It refuses to evaluate price records beyond as_of.

## Reporting threshold

The default minimum is 20 matured signals for a public aggregate hit rate
and mean excess return. Smaller sets only show status and per-event
simulation values, which are insufficient to claim efficacy. A 20-event
threshold still does NOT establish statistical significance: correlated
signals, survivorship/selection bias, sector exposure, data adjustments
and reference choice remain critical. Add confidence intervals and matched
baselines before making any investment claim.

Compare analysis vs simple sector/index baselines on the same decision dates,
and only use evidence publicly available by those dates. Outcomes remain
observational, not attributable to the research tool.

Do not automatically feed results into broker orders or decisions.
