"""Read-only MiroFish report import: no live simulation or market forecasts.

Accepts a JSON export of GET /api/report/<report_id> from a locally run
MiroFish instance. Raw markdown is treated as untrusted, hypothetical output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

IDENTIFIER = re.compile(r"^(report|sim)_[a-zA-Z0-9_-]{1,100}$")


def parse_mirofish_report(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("Expected successful MiroFish report response")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Missing MiroFish report data")
    report_id = data.get("report_id")
    simulation_id = data.get("simulation_id")
    if (not isinstance(report_id, str) or not IDENTIFIER.fullmatch(report_id)
            or not isinstance(simulation_id, str)
            or not IDENTIFIER.fullmatch(simulation_id)
            or not simulation_id.startswith("sim_")):
        raise ValueError("Invalid MiroFish report identifiers")
    if data.get("status") != "completed":
        raise ValueError("Cannot import incomplete simulation report")
    markdown = data.get("markdown_content")
    if not isinstance(markdown, str) or not markdown.strip() or len(markdown) > 500_000:
        raise ValueError("Empty or oversized report content")
    # Never evaluate markdown or treat simulation as sourced market evidence.
    return {
        "kind": "hypothetical_multiagent_scenario",
        "origin": "mirofish_report_export",
        "report_id": report_id,
        "simulation_id": simulation_id,
        "status": "awaits_analyst_review",
        "markdown_content": markdown,
        "created_at": data.get("created_at"),
        "completed_at": data.get("completed_at"),
        "model_quality_validated": False,
        "trading_signal": False,
        "assumption_warning": (
            "This is a synthetic scenario, not a verified statement, calibrated "
            "probability, price forecast or independent investment evidence."
        ),
    }


def import_file(source: str | Path, target: str | Path) -> dict:
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    report = parse_mirofish_report(payload)
    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {k: v for k, v in report.items() if k != "markdown_content"}


def main(argv=None):
    p = argparse.ArgumentParser(description="Validate and label a locally exported MiroFish report")
    p.add_argument("source")
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    print(json.dumps(import_file(args.source, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
