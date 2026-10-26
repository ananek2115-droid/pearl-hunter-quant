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
