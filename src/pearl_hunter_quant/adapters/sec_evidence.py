"""Offline, no-network intake of a PRIVATE SEC evidence export v1.

The source repository is private. Do not commit real export JSON to QUANT.
Outputs a data-availability/review report, NOT a candidate score or order.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

ACC = re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")
ALLOWED_STATUS = {"complete", "partial", "stale"}
COVERAGE_TYPE = "derived_partial_history_not_exhaustive"


def _stamp(raw):
    if not isinstance(raw, str):
        raise ValueError("UTC timestamp string required")
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid timestamp") from None
    if result.tzinfo is None:
        raise ValueError("Timezone offset required")
    return result.astimezone(timezone.utc)


def _symbols(data, *, allow_empty=True):
    if not isinstance(data, list) or (not allow_empty and not data):
        raise ValueError("Expected ticker list")
    if any(not isinstance(t, str) or not SYMBOL.fullmatch(t) for t in data):
        raise ValueError("Invalid ticker in list")
    if len(set(data)) != len(data):
        raise ValueError("Repeated ticker")
    return data


def _positive_decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, float, int)):
        raise ValueError("Invalid reported amount")
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid reported amount") from None
    if not n.is_finite() or n <= 0:
        raise ValueError("Amount must be positive and finite")
    return n


def validate_export(data: dict) -> dict:
    """Fail closed on malformed metadata, references and coverage. Pure function."""
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    if data.get("source") != "pearl-hunter-sec" or data.get("schema_version") != 1:
        raise ValueError("Unknown SEC evidence contract")
    if data.get("research_only") is not True:
        raise ValueError("Research-only marker required")
    state = data.get("scan_health")
    if state not in ALLOWED_STATUS:
        raise ValueError("Unknown scan status")
    scan_time, generated = _stamp(data.get("scan_timestamp_utc")), _stamp(data.get("generated_at_utc"))
    if generated < scan_time:
        raise ValueError("Export cannot predate source scan")
    calculated_age = (generated - scan_time).total_seconds() / 3600
    age = data.get("scan_age_hours")
    if type(age) not in (int, float) or abs(age - calculated_age) > 0.06 or age < 0:
        raise ValueError("Inconsistent scan age")
    if calculated_age > 72 and state != "stale":
        raise ValueError("Overage must be reported stale")
    tickers = _symbols(data.get("watchlist"), allow_empty=False)
    checked = _symbols(data.get("checked_tickers"))
    pending = _symbols(data.get("pending_research_tickers"))
    amendments = _symbols(data.get("amendments_to_review_tickers"))
    base = set(tickers)
    if not (set(checked) | set(pending) | set(amendments)).issubset(base):
        raise ValueError("Report includes unknown ticker")
    invalid_records = data.get("invalid_positive_records")
    if type(invalid_records) is not int or invalid_records < 0:
        raise ValueError("Invalid record count")
    if invalid_records and state == "complete":
        raise ValueError("Cannot claim complete with invalid positive records")
    coverage = data.get("coverage")
    if not isinstance(coverage, list) or len(coverage) != len(tickers):
        raise ValueError("Must explicitly declare all watchlist ticker coverage")
    if {c.get("ticker") for c in coverage if isinstance(c, dict)} != base:
        raise ValueError("Coverage tickers not aligned with watchlist")
    if any(
        not isinstance(c, dict)
        or type(c.get("checked_in_last_scan")) is not bool
        or c["checked_in_last_scan"] != (c["ticker"] in checked)
        or type(c.get("summarized_positive_purchase_filings")) is not int
        or c["summarized_positive_purchase_filings"] < 0
        or c.get("positive_purchase_coverage") != COVERAGE_TYPE
        or type(c.get("further_research_required")) is not bool
        or c["further_research_required"] != (c["ticker"] in pending)
        for c in coverage
    ):
        raise ValueError("Invalid coverage row")
    events = data.get("events")
    if not isinstance(events, list) or len(events) > 5000:
        raise ValueError("Invalid event list")
    actual_counts = {t: 0 for t in tickers}
    unique = set()
    for e in events:
        if not isinstance(e, dict):
            raise ValueError("Event is not an object")
        ticker, acc, cik = e.get("ticker"), e.get("accession"), e.get("cik")
        if (ticker not in base or not isinstance(acc, str) or not ACC.fullmatch(acc)
                or type(cik) is not int or cik <= 0
                or e.get("evidence_type") != "sec_form4_derived_purchase"
                or e.get("first_publication_date", "NOT_SET") is not None
                or e.get("verification") != "source_filing_and_footnotes_must_be_reviewed"):
            raise ValueError("Invalid or unverified SEC event")
        filing_link = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                       f"{acc.replace('-', '')}/{acc}-index.htm")
        if e.get("filing_url") != filing_link:
            raise ValueError("Original SEC link does not match accession")
        if type(e.get("owner_count")) is not int or e["owner_count"] <= 0:
            raise ValueError("Owner count invalid")
        try:
            trade_date = date.fromisoformat(e["transaction_date"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Invalid transaction date") from None
        if trade_date > scan_time.date():
            raise ValueError("Future-dated trade")
        _positive_decimal(e.get("reported_value_usd"))
        identity = (cik, acc)
        if identity in unique:
            raise ValueError("Duplicate SEC filing")
        unique.add(identity)
        actual_counts[ticker] += 1
    for c in coverage:
        if actual_counts[c["ticker"]] != c["summarized_positive_purchase_filings"]:
            raise ValueError("Coverage count mismatch")
    return {
        "schema_version": 1, "kind": "sec_evidence_review_queue",
        "source": "pearl-hunter-sec", "source_scan_timestamp_utc": scan_time.isoformat(),
        "generated_at_utc": generated.isoformat(), "scan_health": state,
        "age_hours_at_export": age, "research_only": True,
        "zero_is_not_absence": True, "scoring_enabled": False,
        "watchlist_size": len(tickers), "checked_ticker_count": len(checked),
        "positive_filing_summaries": len(events), "invalid_positive_records": invalid_records,
        "amendments_to_review_tickers": sorted(amendments),
        "manual_research_tickers": sorted(pending),
        "tickers": [
            {
                "ticker": t,
                "checked_in_last_scan": t in checked,
                "positive_filing_summaries": actual_counts[t],
                "manual_research_required": t in pending,
                "amendment_review_required": t in amendments,
                "coverage": COVERAGE_TYPE,
            }
            for t in tickers
        ],
        "limitations": [
            "No historical public-availability date, do not price-backtest these events.",
            "Zero positive filing summaries does not mean zero insider transactions.",
            "Require the original SEC filing and footnote/ownership review.",
            "Never convert this feed automatically into investment decisions or scores.",
            "Transfer from a private SEC repository to QUANT is deliberately manual and local.",
        ],
    }


def summary_markdown(report: dict) -> str:
    lines = [
        "# SEC / QUANT evidence review",
        "",
        f"Source scan: **{report['source_scan_timestamp_utc']}**",
        f"Export status: **{report['scan_health']}**; age at export: **{report['age_hours_at_export']} h**",
        f"Coverage: **{report['checked_ticker_count']}/{report['watchlist_size']} tickers checked**",
        f"Positive filing summaries in local history: **{report['positive_filing_summaries']}**",
        "",
        "> Research-only. No live brokerage connections, no signals, no candidate scores.",
        "> Zero recorded filings is not proof of no trading. Verify SEC originals.",
        "",
        "| Ticker | Checked | Positive filing summaries | Research | Amendment |",
        "|---|---|---:|---|---|",
    ]
    for entry in report["tickers"]:
        lines.append(
            f"| {entry['ticker']} | {'yes' if entry['checked_in_last_scan'] else 'no'} | "
            f"{entry['positive_filing_summaries']} | "
            f"{'pending' if entry['manual_research_required'] else 'none recorded'} | "
            f"{'review' if entry['amendment_review_required'] else 'none recorded'} |"
        )
    lines += ["", "## Limitations", ""]
    lines += ["- " + item for item in report["limitations"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Local export from private pearl-hunter-sec")
    parser.add_argument("--output", required=True, help="Local Markdown report path")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.source).read_text(encoding="utf-8"))
    report = validate_export(data)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(summary_markdown(report), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "tickers"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
