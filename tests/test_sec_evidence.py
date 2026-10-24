import json
from copy import deepcopy
import pytest

from pearl_hunter_quant.adapters.sec_evidence import (
    main, summary_markdown, validate_export,
)


def source():
    return {
        "schema_version": 1, "source": "pearl-hunter-sec", "research_only": True,
        "scan_timestamp_utc": "2026-10-24T13:00:00+00:00",
        "generated_at_utc": "2026-10-24T14:00:00+00:00",
        "scan_health": "complete", "scan_age_hours": 1.0,
        "watchlist": ["APLD", "NBIS"],
        "checked_tickers": ["APLD"],
        "pending_research_tickers": ["APLD"],
        "amendments_to_review_tickers": ["NBIS"],
        "invalid_positive_records": 0,
        "coverage": [
            {
                "ticker": "APLD", "checked_in_last_scan": True,
                "summarized_positive_purchase_filings": 1,
                "positive_purchase_coverage": "derived_partial_history_not_exhaustive",
                "further_research_required": True,
            },
            {
                "ticker": "NBIS", "checked_in_last_scan": False,
                "summarized_positive_purchase_filings": 0,
                "positive_purchase_coverage": "derived_partial_history_not_exhaustive",
                "further_research_required": False,
            },
        ],
        "events": [
            {
                "ticker": "APLD", "cik": 1144879,
                "accession": "0001391935-26-000009",
                "transaction_date": "2026-10-16",
                "reported_value_usd": "1006686.12",
                "owner_count": 2,
                "filing_url": "https://www.sec.gov/Archives/edgar/data/1144879/000139193526000009/0001391935-26-000009-index.htm",
                "evidence_type": "sec_form4_derived_purchase",
                "verification": "source_filing_and_footnotes_must_be_reviewed",
                "first_publication_date": None,
            },
        ],
    }


def test_valid_export_never_enables_scoring():
    report = validate_export(source())
    assert report["positive_filing_summaries"] == 1
    assert report["manual_research_tickers"] == ["APLD"]
    assert report["amendments_to_review_tickers"] == ["NBIS"]
    assert report["scoring_enabled"] is False
    assert report["research_only"] is True
    assert report["zero_is_not_absence"] is True
    text = summary_markdown(report)
    assert "| APLD | yes | 1 | pending | none recorded |" in text
    assert "| NBIS | no | 0 | none recorded | review |" in text


def test_offline_cli_uses_only_local_files(tmp_path):
    inp, out = tmp_path / "snapshot.json", tmp_path / "report.md"
    inp.write_text(json.dumps(source()), encoding="utf-8")
    assert main([str(inp), "--output", str(out)]) == 0
    assert "SEC / QUANT" in out.read_text(encoding="utf-8")


@pytest.mark.parametrize("change", [
    ("schema_version", 2), ("research_only", False),
    ("scan_health", "published"), ("source", "third-party"),
    ("scan_age_hours", 0.0), ("checked_tickers", ["FAKE"]),
    ("pending_research_tickers", ["FAKE"]), ("coverage", []),
    ("events", [{"ticker": "APLD"}]),
])
def test_fail_closed_on_invalid_contract(change):
    obj = source()
    key, value = change
    obj[key] = value
    with pytest.raises(ValueError):
        validate_export(obj)


def test_fake_sec_link_rejected():
    obj = source()
    obj["events"][0]["filing_url"] = "https://fake-sec.example/Archives/..."
    with pytest.raises(ValueError):
        validate_export(obj)


def test_unknown_publication_time_must_remain_null():
    obj = source()
    obj["events"][0]["first_publication_date"] = "2026-10-17"
    with pytest.raises(ValueError):
        validate_export(obj)


def test_duplicate_or_unmatched_event_count_rejected():
    obj = source()
    obj["events"].append(deepcopy(obj["events"][0]))
    with pytest.raises(ValueError):
        validate_export(obj)
    obj = source()
    obj["coverage"][0]["summarized_positive_purchase_filings"] = 2
    with pytest.raises(ValueError):
        validate_export(obj)


def test_stale_scan_refuses_complete():
    obj = source()
    obj["generated_at_utc"] = "2026-10-29T14:00:00+00:00"
    obj["scan_age_hours"] = 121.0
    with pytest.raises(ValueError):
        validate_export(obj)
    obj["scan_health"] = "stale"
    assert validate_export(obj)["scan_health"] == "stale"


def test_negative_infinite_and_invalid_amounts_rejected():
    for value in ("NaN", "Infinity", "-3", True, None):
        obj = source()
        obj["events"][0]["reported_value_usd"] = value
        with pytest.raises(ValueError):
            validate_export(obj)


def test_zero_summary_is_not_no_insider_activity():
    obj = source()
    obj["coverage"][0]["summarized_positive_purchase_filings"] = 0
    obj["events"] = []
    report = validate_export(obj)
    assert report["zero_is_not_absence"] is True
    assert report["positive_filing_summaries"] == 0


def test_partial_status_and_invalid_record_count():
    obj = source()
    obj["invalid_positive_records"] = 1
    with pytest.raises(ValueError):
        validate_export(obj)
    obj["scan_health"] = "partial"
    assert validate_export(obj)["invalid_positive_records"] == 1
