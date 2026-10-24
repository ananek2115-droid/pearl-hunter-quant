# SEC to QUANT evidence bridge v1

The SEC repository is PRIVATE, while QUANT may be public. Never commit private
exports, API secrets, portfolio records or account information to QUANT.

This module works only on operator-provided local JSON files. It does not
clone SEC, use GitHub credentials, call the SEC API, or send model requests.

## Local commands

From an authorized local clone of the private SEC repository:

    python export_quant_evidence.py --output local_results/sec-evidence.json

Copy the JSON ONLY to a private local folder (not to public GitHub).
With QUANT installed locally:

    python -m pearl_hunter_quant.adapters.sec_evidence local_results/sec-evidence.json --output local_results/sec-review.md

Output is a manual-research Markdown summary with status, timestamps, coverage,
record counts, pending analyst research and amendment-review flags.

## Non-negotiable limitations

- Transaction date does not establish public filing availability. The export
  intentionally has null publication dates. Never backtest against execution
  dates without obtaining historical public release times.
- A zero count in partial stored history does NOT mean no insider activity.
- SEC Form 4 and Form 4/A records must be checked against original documents.
- No scoring, position sizing, brokerage access, or trading recommendations.
- No automatic cross-repository sync; configure separate least-privilege
  artifact transport only after a security review.
- A file can age after export. The report's age is measured at export time,
  NOT at the current time.
