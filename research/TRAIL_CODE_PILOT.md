# Trail-code: controlled context pilot

Upstream: https://github.com/trailhq/Trail-Code (renamed from Graft).
Upstream performance claims are NOT measurements for PEARL HUNTER.
This project installs nothing, grants no permissions, and calls no models.

## Security and local installation
Review a specific release and dependencies before running. Trail-code has
a postinstall script and opt-out telemetry. Use an isolated clone of the
PUBLIC pearl-hunter-quant repo without secrets, broker data or private SEC.
Set DO_NOT_TRACK=1 for privacy. Read-only indexing uses no model key.
Do NOT use the --deep model feature or automatic agent hooks yet.

    export DO_NOT_TRACK=1
    npm install -g @trailhq/trail-code@PINNED_REVIEWED_VERSION
    trail telemetry status
    trail init --dry-run
    trail build
    trail map
    trail ask 'Where does forward_eval reject future-dated events?'

Note: installing globally and postinstall scripts are NOT performed in CI.
Do not run this before reviewing the exact package version. The tool's
init command edits configuration; dry-run only in the first pilot.

## Measure real A/B results
Use the same starting git commit, exact prompt, same model, config,
token accounting and allowed time for baseline vs treatment. Randomize
order to reduce agent familiarity effects. Measure five or more tasks.
Capture actual tool calls, uncached input tokens, seconds and tests passed.
Do not substitute upstream promotional metrics or fictional numbers.
Use examples/trail_pilot_observations.json as schema and populate a LOCAL
copy with observed paired measurements. Keep the tracked fixture empty.

    python -m pearl_hunter_quant.trail_pilot examples/trail_pilot_observations.json --output local_results/trail_benchmark.json

NO_DATA on the empty fixture is intentional. Five correct comparable
pairs produce DESCRIPTIVE_ONLY, not an efficacy or statistical finding.
Never install on production or connect private secrets automatically.

## First actual isolated CLI probe — 2026-10-26

GitHub Actions: https://github.com/ananek2115-droid/pearl-hunter-quant/actions/runs/40346979756

- Published package: `@trailhq/trail-code@0.24.1`, installed with `--ignore-scripts`.
- GitHub Actions public QUANT checkout, no repository credentials persisted,
  `DO_NOT_TRACK=1`, no model calls, no secrets passed to scripts.
- `trail build`: **0.618 seconds** on the runner.
- `trail ask`: **0.265 seconds**, exit 0, named a relevant review module.
- Comparison `git grep`: **0.002 seconds**, two text matches.

**Do not compare these timings as interchangeable workloads**: git grep does
literal text matching; Trail-code returns indexed contextual structure.
This was **one CLI query**, not a randomized matched A/B agent experiment.
Our real-agent token savings, elapsed task time and task-quality improvement
remain **UNKNOWN**; the separate measurement ledger intentionally stays EMPTY.
