from dataclasses import dataclass
from enum import Enum
from typing import Any

class Decision(str, Enum):
    CANDIDATE_NOW = "CANDIDATE_NOW"
    STAGED = "STAGED"
    WAIT = "WAIT"
    REJECT = "REJECT"

@dataclass(frozen=True)
class Candidate:
    symbol: str
    evidence_score: float
    catalyst_score: float
    valuation_score: float
    downside_score: float
    provenance: tuple[str, ...] = ()

@dataclass(frozen=True)
class DecisionCard:
    candidate: Candidate
    decision: Decision
    total_score: float
    reasons: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    research_only: bool = True
    def as_dict(self) -> dict[str, Any]:
        return {"symbol": self.candidate.symbol, "decision": self.decision.value, "total_score": self.total_score, "reasons": list(self.reasons), "missing_evidence": list(self.missing_evidence), "provenance": list(self.candidate.provenance), "research_only": self.research_only}
