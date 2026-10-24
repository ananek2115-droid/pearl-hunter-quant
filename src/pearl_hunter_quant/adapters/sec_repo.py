import json
from pathlib import Path
from ..models import Candidate

def load_candidates(path: str | Path) -> list[Candidate]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("candidates", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list): raise ValueError("expected a JSON list or an object with 'candidates'")
    result = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("symbol"): raise ValueError("each candidate must be an object with a symbol")
        provenance = row.get("provenance", ())
        if isinstance(provenance, str): provenance = (provenance,)
        result.append(Candidate(str(row["symbol"]), row.get("evidence_score", row.get("evidence", 0)), row.get("catalyst_score", row.get("catalyst", 0)), row.get("valuation_score", row.get("valuation", 0)), row.get("downside_score", row.get("downside", 0)), tuple(provenance)))
    return result

def score_file(path: str | Path) -> list[dict]:
    from ..scoring import score_candidate
    return [score_candidate(c).as_dict() for c in load_candidates(path)]
