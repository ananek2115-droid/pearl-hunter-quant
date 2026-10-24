import json
from datetime import datetime, timezone
from copy import deepcopy
import pytest

from pearl_hunter_quant.approved_intake import inspect, main

NOW = "2026-10-24T20:00:00Z"


def empty():
    return {"schema_version": 1, "signals": []}


def approved():
    return {
        "schema_version": 1,
        "signals": [{
            "signal_id": "f" * 24,
            "ticker": "APLD", "recorded_at_utc": "2026-10-24T19:00:00Z",
            "source_public_at_utc": "2026-10-24T18:00:00Z",
            "source_urls": ["https://www.sec.gov/Archives/edgar/synthetic-example"],
            "decision": "analyst_candidate", "card_sha256": "e" * 64,
            "analyst_review": "explicit_manual_confirmation",
        }],
    }


def test_empty_ledger_has_no_claimed_market_alpha():
    result = inspect(empty(), as_of=NOW)
    assert result["approved_candidate_count"] == 0
    assert result["market_performance"] is None
    assert result["publication_time_verified_externally"] is False


def test_valid_registered_candidate_is_only_cohort_intake():
    r = inspect(approved(), as_of=NOW)
    assert r["approved_candidate_count"] == 1
    assert r["tickers"] == ["APLD"]
    assert r["market_performance"] is None
    assert r["immutability_verified_externally"] is False


def test_no_unapproved_candidate_allowed():
    payload = approved()
    payload["signals"][0]["analyst_review"] = "automatically_inferred"
    with pytest.raises(ValueError):
        inspect(payload, as_of=NOW)


def test_missing_card_checksum_rejected():
    payload = approved()
    payload["signals"][0]["card_sha256"] = "unknown"
    with pytest.raises(ValueError):
        inspect(payload, as_of=NOW)


def test_duplicate_card_hash_rejected():
    payload = approved()
    clone = deepcopy(payload["signals"][0])
    clone["signal_id"] = "d" * 24
    payload["signals"].append(clone)
    with pytest.raises(ValueError):
        inspect(payload, as_of=NOW)


def test_future_signal_rejected():
    payload = approved()
    payload["signals"][0]["recorded_at_utc"] = "2026-10-26T10:00:00Z"
    with pytest.raises(ValueError):
        inspect(payload, as_of=NOW)


def test_unpublished_source_rejected():
    payload = approved()
    payload["signals"][0]["source_public_at_utc"] = "2026-10-24T20:01:00Z"
    with pytest.raises(ValueError):
        inspect(payload, as_of=NOW)


def test_wrong_decision_rejected():
    payload = approved()
    payload["signals"][0]["decision"] = "WATCHLIST"
    with pytest.raises(ValueError):
        inspect(payload, as_of=NOW)


def test_bad_timestamp_rejected():
    with pytest.raises(ValueError):
        inspect(approved(), as_of="2026-10-24T20:00:00")


def test_private_file_cli_outputs_local_report(tmp_path):
    a = tmp_path / "ledger.json"
    b = tmp_path / "validated.json"
    a.write_text(json.dumps(empty()), encoding="utf-8")
    assert main(["--ledger", str(a), "--as-of-utc", NOW,
                 "--output", str(b)]) == 0
    report = json.loads(b.read_text(encoding="utf-8"))
    assert report["approved_candidate_count"] == 0
