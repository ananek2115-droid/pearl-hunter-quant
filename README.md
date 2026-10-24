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

## Experimental LLM lab: FreeLLMAPI (optional)

An isolated, read-only `llm_lab` evaluates numeric facts and source IDs on
synthetic fixtures. **No router or remote model is installed and no live keys
are required for CI.** See [LLM_LAB.md](research/LLM_LAB.md).

    python -m pearl_hunter_quant.llm_lab

Real local comparison requires a separately configured FreeLLMAPI gateway and
explicit `--live --model MODEL_ID`; keep the unified proxy key in the local
`FREELLMAPI_API_KEY` environment variable, never the repository. Results do
not produce trading signals.

## Experimental MiroFish scenario intake (offline only)

The `scenario_lab` importer accepts an authorized local JSON export of a
**completed** MiroFish simulation report and marks it as hypothetical,
unverified, and requiring analyst review. It does not run MiroFish, call a
model, or assert real-world predictive power. See
[SCENARIO_LAB.md](research/SCENARIO_LAB.md).

    python -m pearl_hunter_quant.scenario_lab local_results/report.json --output local_results/scenario.json

Never commit sensitive export files or portfolio data.


## Private SEC → QUANT bridge (local only)

The private SEC repository now has a versioned, read-only evidence exporter.
QUANT accepts the JSON locally, validates all source references, metadata and
event counts, and produces a human review report without brokerage access or
model inference. See [SEC evidence bridge](research/SEC_EVIDENCE_BRIDGE.md).

    python -m pearl_hunter_quant.adapters.sec_evidence local_results/sec-evidence.json --output local_results/sec-review.md

Never commit the exported JSON to the public QUANT repository.
Scans do not establish actual insider positions or buy/sell recommendations.

## Local FreeLLMAPI network hardening

The optional router client refuses non-loopback endpoints, ambient proxy
routing and HTTP redirects. Live mode still requires an operator-provided
local key and explicit approval. Benchmarks are not sent to CI providers.

## Measured effectiveness (prospective research only)

The `forward_eval` module evaluates ONLY analyst-approved candidate ideas
recorded before future price moves against adjusted benchmark prices,
with 5/20/60-session cohorts and conservative minimum-sample rules.
It cannot infer market profitability from raw SEC filing alerts or watchlists.

The initial real approved-signal ledger has not been populated. Therefore
**investment hit rate and excess return are still N/A**, not a marketing
success percentage. The shipped example contains no signals and synthetic
benchmark prices for CI testing only. Read
[Prospective evaluation methodology](research/PROSPECTIVE_EVALUATION.md).

    python -m pearl_hunter_quant.forward_eval --signals examples/forward_signals_synthetic.json --prices examples/forward_prices_synthetic.json --as-of-utc 2026-10-24T23:59:59Z --output local_results/forward_eval.json

## Private analyst-approved signals from SEC

The SEC project now has a **private** prospective journal, initially with
**zero approved stock ideas**. QUANT's `approved_intake` validates the journal
locally (required approval marker, time bounds, card hash and source links).
It does not open private GitHub, autonomously approve or execute trades.

    python -m pearl_hunter_quant.approved_intake --ledger local_results/approved_signals.json --as-of-utc 2026-10-24T23:59:59Z --output local_results/ledger_audit.json

This is only a format/authorization-metadata check. Independently verify
original source publication times and the Git history proving prospective
creation. For investment outcome analysis use `forward_eval` with real
independent price data, once the cohort has matured.
