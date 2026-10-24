"""Validate manually approved private SEC signal ledger before QUANT evaluation.

This module never downloads the private repo or copies a ledger to GitHub.
No historical timestamps are independently authenticated by this function;
commit history and original issuer-publication times must be reviewed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .forward_eval import validate_signals

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def inspect(ledger: dict, *, as_of: str | datetime) -> dict:
    if isinstance(as_of, str):
        as_of = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise ValueError("An actual timezone-aware cutoff time is required")
    as_of = as_of.astimezone(timezone.utc)
    records = validate_signals(ledger, as_of=as_of)
    seen_card_hashes = set()
    for raw in ledger["signals"]:
        if raw.get("analyst_review") != "explicit_manual_confirmation":
            raise ValueError("Ledger contains an unapproved candidate")
        if (not isinstance(raw.get("card_sha256"), str)
                or not SHA256.fullmatch(raw["card_sha256"])):
            raise ValueError("Unverifiable analyst card checksum")
        if raw["card_sha256"] in seen_card_hashes:
            raise ValueError("Same analyst card recorded more than once")
        seen_card_hashes.add(raw["card_sha256"])
    return {
        "kind": "approved_signals_intake",
        "as_of_utc": as_of.isoformat(),
        "approved_candidate_count": len(records),
        "tickers": sorted({r["ticker"] for r in records}),
        "signal_ids": [r["signal_id"] for r in records],
        "ledger_compatible_with_forward_eval": True,
        "publication_time_verified_externally": False,
        "immutability_verified_externally": False,
        "market_performance": None,
        "notes": [
            "Human confirmation marker and schema are present; this does not prove past human consent.",
            "Review PRIVATE Git commit timestamp and original issuer release timestamps.",
            "No quote, valuation, market return or alpha is inferred from approval alone.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, help="Private local SEC approved_signals.json")
    parser.add_argument("--as-of-utc", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
    report = inspect(payload, as_of=args.as_of_utc)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"approved_candidate_count": report["approved_candidate_count"],
                      "validated_format": True, "market_performance": None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
