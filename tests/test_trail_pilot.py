import copy
import json
import pytest
from pearl_hunter_quant.trail_pilot import evaluate, main

SHA = "a" * 40
PROMPT = "b" * 64

def sample(task="locate-risk", variant="baseline", duration=10, passed=True):
    return {
        "task_id": task, "variant": variant, "starting_commit": SHA,
        "prompt_sha256": PROMPT, "measurement_source": "agent_usage_log",
        "elapsed_seconds": duration, "tool_calls": 10,
        "uncached_input_tokens": 2000, "tests_passed": passed,
    }

def test_no_measurements_no_verdict():
    r = evaluate({"schema_version":1,"observations":[]})
    assert r["status"] == "NO_DATA" and r["metrics"] is None

def test_matched_pairs_descriptive_only():
    rows = []
    for i in range(5):
        rows += [sample("task"+str(i), "baseline",100),sample("task"+str(i),"trail",80)]
    r = evaluate({"schema_version":1,"observations":rows})
    assert r["status"] == "DESCRIPTIVE_ONLY"
    assert r["completed_valid_pairs"] == 5
    assert r["metrics"]["elapsed_seconds"]["median_paired_reduction_pct"] == 20.0

def test_regression_failure_blocks_results():
    r=evaluate({"schema_version":1,"observations":[sample(),sample(variant="trail",duration=1,passed=False)]})
    assert r["status"] == "NO_DATA" and r["regression_failed_pairs"] == ["locate-risk"]

def test_missing_treatment_does_not_count():
    r=evaluate({"schema_version":1,"observations":[sample()]})
    assert r["status"] == "NO_DATA" and r["incomplete_pairs"] == ["locate-risk"]

def test_different_commit_or_prompt_rejected():
    base=sample()
    candidate=sample(variant="trail")
    candidate["starting_commit"]="c"*40
    with pytest.raises(ValueError):
        evaluate({"schema_version":1,"observations":[base,candidate]})
    candidate["starting_commit"]=SHA
    candidate["prompt_sha256"]="d"*64
    with pytest.raises(ValueError):
        evaluate({"schema_version":1,"observations":[base,candidate]})

@pytest.mark.parametrize("field,value",[
    ("elapsed_seconds",-1),("elapsed_seconds",float("nan")),
    ("tool_calls",1.7),("tool_calls",-3),
    ("uncached_input_tokens","500"),("tests_passed","yes"),
    ("measurement_source","guessed"),
])
def test_invalid_record_rejected(field,value):
    row=sample()
    row[field]=value
    with pytest.raises(ValueError):
        evaluate({"schema_version":1,"observations":[row]})

def test_duplicate_and_synthetic_disallowed():
    row=sample()
    with pytest.raises(ValueError):
        evaluate({"schema_version":1,"observations":[row,copy.deepcopy(row)]})
    with pytest.raises(ValueError):
        evaluate({"schema_version":1,"contains_synthetic_measurements":True,"observations":[row]})

def test_cli_without_data(tmp_path):
    a,b=tmp_path/"a.json",tmp_path/"b.json"
    a.write_text(json.dumps({"schema_version":1,"observations":[]}),encoding="utf-8")
    assert main([str(a),"--output",str(b)])==0
    assert json.loads(b.read_text(encoding="utf-8"))["status"]=="NO_DATA"
