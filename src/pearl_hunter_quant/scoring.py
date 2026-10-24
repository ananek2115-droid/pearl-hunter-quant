from .models import Candidate, Decision, DecisionCard

def _bounded(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

def score_candidate(candidate: Candidate) -> DecisionCard:
    values = {"evidence": _bounded(candidate.evidence_score), "catalyst": _bounded(candidate.catalyst_score), "valuation": _bounded(candidate.valuation_score), "downside": _bounded(candidate.downside_score)}
    total = round(sum(values.values()) / 4, 4)
    missing = tuple(name for name, value in values.items() if value == 0)
    reasons = tuple(f"{name}={value:.2f}" for name, value in values.items())
    if not candidate.provenance: missing = tuple(sorted(set(missing + ("provenance",))))
    if values["evidence"] < 0.5 or "provenance" in missing: decision = Decision.WAIT
    elif total >= 0.8: decision = Decision.CANDIDATE_NOW
    elif total >= 0.6: decision = Decision.STAGED
    elif total < 0.35: decision = Decision.REJECT
    else: decision = Decision.WAIT
    return DecisionCard(candidate, decision, total, reasons, missing)
