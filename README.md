# pearl-hunter-quant

Deterministic, research-only quantitative scoring for PEARL HUNTER.

## Scope

This repository does not connect to a broker, place orders, calculate position sizes, promise returns, or replace analyst judgment. It scores only evidence explicitly supplied by the caller.

## Architecture

- src/pearl_hunter_quant/models.py: immutable candidate and decision-card types.
- src/pearl_hunter_quant/scoring.py: bounded deterministic scoring gate.
- src/pearl_hunter_quant/adapters/sec_repo.py: file-based adapter for a normalized JSON export from pearl-hunter-sec.
- tests/: behavior and safety-boundary tests.
- .github/workflows/ci.yml: Python 3.11 CI.

The adapter is file-based and does not assume that the private SEC repository is importable at runtime or bypass GitHub permissions.

## Input

    {"candidates": [{"symbol": "ABC", "evidence": 0.8, "catalyst": 0.7, "valuation": 0.6, "downside": 0.7, "provenance": ["sec://filing/1"]}]}

Scores are bounded to 0–1. Missing evidence defaults to zero and keeps the result conservative. Provenance is required for CANDIDATE_NOW.

## Decisions

- CANDIDATE_NOW: average score at least 0.80, evidence and provenance present.
- STAGED: average score at least 0.60.
- WAIT: insufficient evidence or an intermediate score.
- REJECT: average score below 0.35.

WAIT is a research state, not an instruction to trade. Production integration should retain dated primary-source links and expose missing evidence.

## Local checks

    python -m pip install -e .
    pytest -q
