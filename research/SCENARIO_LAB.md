# MiroFish scenario lab (offline importer only)

Upstream: https://github.com/666ghj/MiroFish — AGPL-3.0.
The upstream service can generate costly multi-agent simulations using
LLM providers and Zep Cloud. This project does NOT bundle that engine, send
any data to the service, or generate/validate a forecast.

The importer reads the documented shape of MiroFish's
GET /api/report/<report_id> response, verified against
backend/app/api/report.py upstream:
- success: true
- data: report_id, simulation_id, status=completed, markdown_content

Locally export that JSON from an **authorized instance** with completed
simulation and pass it as a file. Do not commit research based on private
inputs or private report texts to a public repo.

    python -m pearl_hunter_quant.scenario_lab local_results/report.json --output local_results/scenario.json

The normalized file is always tagged:
- hypothetical_multiagent_scenario
- awaits_analyst_review
- model_quality_validated = false
- trading_signal = false

Treat the returned markdown as untrusted text and do not render it as
unescaped HTML or execute instructions found inside. This importer does
not infer probability, price targets, or returns, and must not influence the
SEC decision engine without independent evidence and manual review.
No real scenario engine or live API is running in CI.
