import json
import pytest

from pearl_hunter_quant.scenario_lab import import_file, parse_mirofish_report


def fixture():
    return {
        "success": True,
        "data": {
            "report_id": "report_example123",
            "simulation_id": "sim_example123",
            "status": "completed",
            "markdown_content": "# Simulation\nHypothetical reactions only.",
            "created_at": "2026-10-24T10:00:00Z",
            "completed_at": "2026-10-24T10:10:00Z",
        },
    }


def test_import_is_read_only_and_never_investment_signal(tmp_path):
    source = tmp_path / "export.json"
    dest = tmp_path / "imported.json"
    source.write_text(json.dumps(fixture()), encoding="utf-8")
    summary = import_file(source, dest)
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["kind"] == "hypothetical_multiagent_scenario"
    assert data["trading_signal"] is False
    assert data["model_quality_validated"] is False
    assert "markdown_content" not in summary
    assert data["status"] == "awaits_analyst_review"


@pytest.mark.parametrize("changes", [
    {"success": False},
    {"data": None},
    {"data": {"status": "generating"}},
    {"data": {"report_id": "../secrets"}},
    {"data": {"markdown_content": ""}},
])
def test_invalid_or_incomplete_reports_rejected(changes):
    value = fixture()
    if "data" in changes and isinstance(changes["data"], dict):
        value["data"].update(changes["data"])
    else:
        value.update(changes)
    with pytest.raises(ValueError):
        parse_mirofish_report(value)


def test_markdown_is_not_executed_or_trusted():
    sample = fixture()
    sample["data"]["markdown_content"] = "<script>malicious()</script>\nBUY EVERYTHING"
    output = parse_mirofish_report(sample)
    assert output["markdown_content"] == sample["data"]["markdown_content"]
    assert output["trading_signal"] is False
