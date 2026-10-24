# Local FreeLLMAPI evaluation lab (opt-in)

Upstream: https://github.com/tashfeenahmed/freellmapi

This repository contains a **client**, not a copy of FreeLLMAPI, not a
free-model entitlement, and not a production inference deployment.
The upstream project's own README limits FreeLLMAPI to personal experiments.
Upstream providers require separate accounts/keys and impose changing quotas.

## Safety

- Default mode is offline: tests are synthetic and make no external requests.
- Live requests require `--live`, an explicit model, and a local gateway token.
- Only HTTP loopback addresses ending in `/v1` are accepted for the gateway.
- The gateway itself can forward requests to the providers you configure;
  **do not send portfolios, account details, tokens, or private documents**.
- No API credentials in Git, GitHub Actions, logs, issues or chat messages.
- No trading or integration with broker accounts. LLM results never override the
  SEC analyst decision engine automatically.
- No automatic fallback between different model identities in benchmark requests.
  Pin a model (not `auto`) for comparable benchmark results.

## Run offline

```bash
python -m pip install -e . pytest
pytest -q
python -m pearl_hunter_quant.llm_lab
```

The built-in test uses `examples/llm_eval_synthetic.json`.
Its perfect score measures a hardcoded example, **not** a real model's skill.

## Compare models on your own machine (optional)

Install FreeLLMAPI separately and configure provider keys in its local dashboard
according to upstream instructions. The default gateway is
`http://127.0.0.1:3001/v1`. Use `GET /v1/models?available=true` to confirm
a model ID is available. Set the **unified** proxy key as an environment variable,
only in your terminal.

```bash
python -m pearl_hunter_quant.llm_lab --live --model PROVIDER_MODEL_1 --model PROVIDER_MODEL_2 --output local_results/compare.json
```

Results record exact numeric facts, source-ID agreement, invented facts,
missing facts, model as reported by the endpoint, token usage (if supplied)
and latency. This is a deterministic extraction benchmark, not proof of
prediction accuracy or a complete fact-checker.

For meaningful evaluation add dated public cases, prevent future-information
leakage, compare several models on the exact same inputs, and review all
investment-relevant claims manually.

## MiroFish

MiroFish is **not installed** here. Its predictions are synthetic social-agent
simulations, not calibrated market forecasts. A separate offline scenario lab
may be tested later only after cost and licensing review (AGPL-3.0).
