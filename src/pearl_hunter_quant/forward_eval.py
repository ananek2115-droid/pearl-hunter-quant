"""Point-in-time research cohort evaluation (never a trading engine).

Only prospectively recorded analyst-review events are considered. Candidate
research queues and SEC filings are NOT automatically investment signals.
Prices must be externally supplied, adjusted, verified and date-aligned.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import statistics
from urllib.parse import urlparse

SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
HORIZONS = (5, 20, 60)
MIN_COHORT = 20


def _day(value):
    if not isinstance(value, str):
        raise ValueError("Date must be ISO string")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid date") from None


def _stamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be ISO string")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid timestamp") from None
    if stamp.tzinfo is None:
        raise ValueError("Timestamp needs timezone")
    return stamp.astimezone(timezone.utc)


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (float, int, str)):
        raise ValueError("Positive numeric adjusted close required")
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid price") from None
    if not n.is_finite() or n <= 0:
        raise ValueError("Adjusted close must be finite and positive")
    return n


def validate_signals(data, *, as_of):
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported signals ledger")
    rows = data.get("signals")
    if not isinstance(rows, list):
        raise ValueError("Expected signals array")
    seen = set()
    result = []
    for s in rows:
        if not isinstance(s, dict):
            raise ValueError("Invalid signal row")
        sid, ticker = s.get("signal_id"), s.get("ticker")
        if (not isinstance(sid, str) or not IDENTIFIER.fullmatch(sid) or sid in seen
                or not isinstance(ticker, str) or not SYMBOL.fullmatch(ticker)
                or ticker == "SPY"):
            raise ValueError("Duplicate/bad signal ID or ticker")
        recorded = _stamp(s.get("recorded_at_utc"))
        public = _stamp(s.get("source_public_at_utc"))
        if not public <= recorded <= as_of:
            raise ValueError("Unpublished, postdated, or future event")
        if s.get("decision") != "analyst_candidate":
            raise ValueError("Only explicit, pre-recorded analyst candidates are measurable")
        urls = s.get("source_urls")
        if not isinstance(urls, list) or not urls or len(urls) > 10:
            raise ValueError("Signal needs referenced primary sources")
        for url in urls:
            if not isinstance(url, str):
                raise ValueError("Source URL must be a string")
            p = urlparse(url)
            if p.scheme != "https" or not p.netloc or p.username or p.password:
                raise ValueError("Source must be HTTPS URL")
        result.append({
            "signal_id": sid,
            "ticker": ticker,
            "recorded_at_utc": recorded.isoformat(),
            "signal_date": recorded.date(),
            "source_public_at_utc": public.isoformat(),
            "source_count": len(urls),
        })
        seen.add(sid)
    return result


def validate_prices(data, *, as_of_date):
    """Require independently supplied adjusted closes; no network access."""
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unknown price data schema")
    if data.get("price_type") != "adjusted_close" or not data.get("source"):
        raise ValueError("Price provenance and adjusted_close required")
    rows = data.get("prices")
    if not isinstance(rows, list):
        raise ValueError("Expected price observations list")
    lookup = defaultdict(dict)
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("Bad price row")
        symbol = item.get("ticker")
        if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
            raise ValueError("Invalid price ticker")
        trading_date = _day(item.get("date"))
        price = _decimal(item.get("adjusted_close"))
        if trading_date > as_of_date:
            continue
        if trading_date in lookup[symbol]:
            raise ValueError("Duplicate adjusted price for a ticker/date")
        lookup[symbol][trading_date] = price
    return lookup


def evaluate(signals_data, prices_data, *, as_of, horizons=HORIZONS,
             minimum_cohort=MIN_COHORT, benchmark="SPY", roundtrip_cost_bps=0):
    as_of = _stamp(as_of) if isinstance(as_of, str) else as_of
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    if (not isinstance(horizons, (tuple, list)) or not horizons
            or any(type(h) is not int or h <= 0 or h > 252 for h in horizons)
            or len(set(horizons)) != len(horizons)):
        raise ValueError("Use unique valid trading-session horizons")
    if type(minimum_cohort) is not int or minimum_cohort < 2:
        raise ValueError("minimum_cohort must be at least 2")
    if type(roundtrip_cost_bps) not in (int, float) or not 0 <= roundtrip_cost_bps <= 200:
        raise ValueError("Round-trip basis points must be 0..200")
    signals = validate_signals(signals_data, as_of=as_of)
    prices = validate_prices(prices_data, as_of_date=as_of.date())
    if benchmark not in prices:
        raise ValueError("Benchmark adjusted prices missing")
    benchmark_dates = sorted(prices[benchmark])
    outcomes = []
    for s in signals:
        symbol_prices = prices.get(s["ticker"], {})
        possible = [i for i, d in enumerate(benchmark_dates) if d > s["signal_date"]]
        start_ix = possible[0] if possible else None
        for horizon in horizons:
            row = {"signal_id": s["signal_id"], "ticker": s["ticker"],
                   "recorded_at_utc": s["recorded_at_utc"],
                   "horizon_sessions": horizon, "benchmark": benchmark}
            if start_ix is None:
                row["status"] = "no_future_session"
            else:
                entry_day = benchmark_dates[start_ix]
                row["entry_date"] = entry_day.isoformat()
                if entry_day not in symbol_prices:
                    row["status"] = "missing_entry_price"
                elif start_ix + horizon >= len(benchmark_dates):
                    row["status"] = "immature"
                else:
                    exit_day = benchmark_dates[start_ix + horizon]
                    row["exit_date"] = exit_day.isoformat()
                    if exit_day not in symbol_prices:
                        row["status"] = "missing_exit_price"
                    else:
                        gross = symbol_prices[exit_day] / symbol_prices[entry_day] - 1
                        ref = prices[benchmark][exit_day] / prices[benchmark][entry_day] - 1
                        net = gross - Decimal(str(roundtrip_cost_bps)) / Decimal("10000")
                        row.update({
                            "status": "matured",
                            "stock_net_return": round(float(net), 6),
                            "benchmark_return": round(float(ref), 6),
                            "excess_return": round(float(net - ref), 6),
                            "outperformed": bool(net > ref),
                            "assumption": "next SPY session adjusted-close entry; same session exit after horizon",
                        })
            outcomes.append(row)
    cohorts = []
    for horizon in horizons:
        subset = [x for x in outcomes if x["horizon_sessions"] == horizon]
        matured = [x for x in subset if x["status"] == "matured"]
        enough = len(matured) >= minimum_cohort
        cohorts.append({
            "horizon_sessions": horizon, "signals": len(subset),
            "matured": len(matured), "immature": sum(x["status"] == "immature" for x in subset),
            "missing_or_no_price": sum(x["status"] in
                 ("missing_entry_price", "missing_exit_price", "no_future_session") for x in subset),
            "status": "measurable" if enough else "insufficient_sample",
            "mean_excess_return": (round(statistics.mean(x["excess_return"] for x in matured), 6)
                                   if enough else None),
            "hit_rate_vs_benchmark": (round(sum(x["outperformed"] for x in matured) / len(matured), 4)
                                      if enough else None),
            "note": "Return estimates are observational, not causal alpha; correlated/selected signals need controlled tests.",
        })
    return {
        "schema_version": 1, "as_of_utc": as_of.isoformat(),
        "mode": "prospective_research_evaluation_only",
        "signal_count": len(signals), "benchmark": benchmark,
        "roundtrip_cost_bps": roundtrip_cost_bps,
        "minimum_cohort": minimum_cohort,
        "cohorts": cohorts, "outcomes": outcomes,
        "warnings": [
            "No signals? No efficacy conclusion. Candidate queue is NOT an analyst-approved signal.",
            "Historical recorded_at fields alone cannot prove an immutable timestamp: use append-only, version-controlled storage.",
            "Adjusted-close backtests assume next-session closing prices and are not executable fills.",
            "Source publication timestamp must be verified independently.",
            "Survivorship bias, corporate actions, delistings, liquidity, sector concentration and data vendor quality remain material.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--signals", required=True)
    p.add_argument("--prices", required=True)
    p.add_argument("--as-of-utc", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--min-cohort", type=int, default=MIN_COHORT)
    args = p.parse_args(argv)
    signals = json.loads(Path(args.signals).read_text(encoding="utf-8"))
    prices = json.loads(Path(args.prices).read_text(encoding="utf-8"))
    report = evaluate(signals, prices, as_of=args.as_of_utc,
                      minimum_cohort=args.min_cohort)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "signal_count": report["signal_count"],
        "cohorts": [{k: v for k, v in row.items() if k != "note"}
                    for row in report["cohorts"]],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
