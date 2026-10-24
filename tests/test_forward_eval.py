import json
from copy import deepcopy
import pytest

from pearl_hunter_quant.forward_eval import evaluate, main

AS_OF = "2026-10-24T20:00:00Z"
DAYS = ["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16",
        "2026-10-17", "2026-10-20", "2026-10-21"]


def fixtures():
    signal = {
        "schema_version": 1,
        "signals": [
            {"signal_id": "synthetic-1", "ticker": "DEMO",
             "recorded_at_utc": "2026-10-10T10:00:00Z",
             "source_public_at_utc": "2026-10-09T10:00:00Z",
             "source_urls": ["https://www.sec.gov/Archives/example"],
             "decision": "analyst_candidate"},
            {"signal_id": "synthetic-2", "ticker": "FAKE",
             "recorded_at_utc": "2026-10-10T10:00:00Z",
             "source_public_at_utc": "2026-10-09T10:00:00Z",
             "source_urls": ["https://www.sec.gov/Archives/example"],
             "decision": "analyst_candidate"}
        ]
    }
    prices = {"schema_version": 1, "price_type": "adjusted_close",
              "source": "SYNTHETIC_TEST_ONLY", "prices": []}
    for ticker, values in [
        ("SPY", [100, 100, 101, 101, 102, 103, 104]),
        ("DEMO", [100, 100, 100, 100, 105, 115, 118]),
        ("FAKE", [100, 100, 100, 99, 98, 96, 95])
    ]:
        prices["prices"].extend(
            {"ticker": ticker, "date": day, "adjusted_close": val}
            for day, val in zip(DAYS, values)
        )
    return signal, prices


def test_two_matured_synthetic_signals_with_benchmark():
    signals, prices = fixtures()
    result = evaluate(signals, prices, as_of=AS_OF, minimum_cohort=2)
    c5 = result["cohorts"][0]
    assert c5["horizon_sessions"] == 5
    assert c5["matured"] == 2
    assert c5["status"] == "measurable"
    assert c5["hit_rate_vs_benchmark"] == .5
    assert c5["mean_excess_return"] == -.025
    assert [r["entry_date"] for r in result["outcomes"] if r["horizon_sessions"] == 5] == [DAYS[0], DAYS[0]]
    assert [r["exit_date"] for r in result["outcomes"] if r["horizon_sessions"] == 5] == [DAYS[5], DAYS[5]]
    assert result["cohorts"][1]["status"] == "insufficient_sample"


def test_default_minimum_sample_refuses_unjustified_success():
    signals, prices = fixtures()
    report = evaluate(signals, prices, as_of=AS_OF)
    assert report["cohorts"][0]["matured"] == 2
    assert report["cohorts"][0]["mean_excess_return"] is None
    assert report["cohorts"][0]["hit_rate_vs_benchmark"] is None


def test_empty_signal_ledger_means_not_measurable():
    signals, prices = fixtures()
    signals["signals"] = []
    result = evaluate(signals, prices, as_of=AS_OF)
    assert result["signal_count"] == 0
    assert all(c["status"] == "insufficient_sample" and c["matured"] == 0 for c in result["cohorts"])


def test_fees_reduce_net_returns():
    signals, prices = fixtures()
    base = evaluate(signals, prices, as_of=AS_OF, minimum_cohort=2)
    fee = evaluate(signals, prices, as_of=AS_OF, minimum_cohort=2, roundtrip_cost_bps=10)
    assert fee["cohorts"][0]["mean_excess_return"] == base["cohorts"][0]["mean_excess_return"] - .001


def test_maturity_is_relative_to_asof_not_final_available_prices():
    signals, prices = fixtures()
    report = evaluate(signals, prices, as_of="2026-10-17T23:00:00Z")
    assert report["cohorts"][0]["matured"] == 0
    assert report["cohorts"][0]["immature"] == 2


def test_refuse_signal_with_future_or_unpublished_source():
    signals, prices = fixtures()
    signals["signals"][0]["source_public_at_utc"] = "2026-10-12T10:00:00Z"
    with pytest.raises(ValueError):
        evaluate(signals, prices, as_of=AS_OF)
    signals, prices = fixtures()
    signals["signals"][0]["recorded_at_utc"] = "2026-10-26T10:00:00Z"
    with pytest.raises(ValueError):
        evaluate(signals, prices, as_of=AS_OF)


def test_research_queue_is_not_a_signal():
    signals, prices = fixtures()
    signals["signals"][0]["decision"] = "RESEARCH_REQUIRED"
    with pytest.raises(ValueError):
        evaluate(signals, prices, as_of=AS_OF)


def test_duplicate_signal_or_undocumented_source_rejected():
    signals, prices = fixtures()
    signals["signals"].append(deepcopy(signals["signals"][0]))
    with pytest.raises(ValueError):
        evaluate(signals, prices, as_of=AS_OF)
    signals, prices = fixtures()
    signals["signals"][0]["source_urls"] = ["http://unverified.example/test"]
    with pytest.raises(ValueError):
        evaluate(signals, prices, as_of=AS_OF)


@pytest.mark.parametrize("bad", [0, -5, float("nan"), "Infinity", True])
def test_invalid_adjusted_close_rejected(bad):
    signals, prices = fixtures()
    prices["prices"][0]["adjusted_close"] = bad
    with pytest.raises(ValueError):
        evaluate(signals, prices, as_of=AS_OF)


def test_duplicate_price_and_missing_benchmark_rejected():
    signals, prices = fixtures()
    prices["prices"].append(deepcopy(prices["prices"][0]))
    with pytest.raises(ValueError):
        evaluate(signals, prices, as_of=AS_OF)
    signals, prices = fixtures()
    prices["prices"] = [x for x in prices["prices"] if x["ticker"] != "SPY"]
    with pytest.raises(ValueError):
        evaluate(signals, prices, as_of=AS_OF)


def test_missing_entry_and_exit_prices_explicit():
    signals, prices = fixtures()
    prices["prices"] = [x for x in prices["prices"]
                        if not (x["ticker"] == "DEMO" and x["date"] == DAYS[0])]
    report = evaluate(signals, prices, as_of=AS_OF)
    assert report["outcomes"][0]["status"] == "missing_entry_price"
    signals, prices = fixtures()
    prices["prices"] = [x for x in prices["prices"]
                        if not (x["ticker"] == "DEMO" and x["date"] == DAYS[5])]
    report = evaluate(signals, prices, as_of=AS_OF)
    assert report["outcomes"][0]["status"] == "missing_exit_price"


def test_offline_cli_roundtrip(tmp_path):
    signals, prices = fixtures()
    a, b, c = tmp_path/"signals.json", tmp_path/"prices.json", tmp_path/"report.json"
    a.write_text(json.dumps(signals), encoding="utf-8")
    b.write_text(json.dumps(prices), encoding="utf-8")
    assert main(["--signals", str(a), "--prices", str(b),
                 "--as-of-utc", AS_OF, "--output", str(c)]) == 0
    report = json.loads(c.read_text(encoding="utf-8"))
    assert report["cohorts"][0]["status"] == "insufficient_sample"
