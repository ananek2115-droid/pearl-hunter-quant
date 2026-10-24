import json
from pearl_hunter_quant import Candidate, Decision, score_candidate
from pearl_hunter_quant.adapters.sec_repo import load_candidates, score_file

def test_missing_provenance_cannot_be_candidate_now():
    card = score_candidate(Candidate("ABC", 1, 1, 1, 1))
    assert card.decision is Decision.WAIT
    assert "provenance" in card.missing_evidence

def test_high_quality_evidence_is_candidate_now():
    card = score_candidate(Candidate("ABC", 1, 1, 1, 1, ("sec://filing/1",)))
    assert card.decision is Decision.CANDIDATE_NOW

def test_adapter_accepts_sec_export(tmp_path):
    path = tmp_path / "export.json"
    path.write_text(json.dumps({"candidates": [{"symbol": "ABC", "evidence": .8, "catalyst": .7, "valuation": .6, "downside": .7, "provenance": ["sec://filing/1"]}]}), encoding="utf-8")
    assert load_candidates(path)[0].symbol == "ABC"
    assert score_file(path)[0]["decision"] == "STAGED"

def test_invalid_shape_is_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"candidates": {}}), encoding="utf-8")
    try: load_candidates(path)
    except ValueError: pass
    else: raise AssertionError("invalid shape accepted")
