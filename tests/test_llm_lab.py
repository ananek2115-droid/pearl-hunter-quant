import json
from urllib.request import Request
import pytest

from pearl_hunter_quant.llm_lab import (
    EvalCase, GatewayError, LocalGateway, benchmark, load_cases, main,
    messages_for_case, score_response,
)


@pytest.fixture
def example():
    return EvalCase.parse({
        "case_id": "synthetic",
        "evidence": [{"source_id": "fake:source", "text": "Synthetic earnings: 120 million."}],
        "expected": [{"fact_id": "revenue", "source_id": "fake:source", "value": 120}],
        "offline_response": {"findings": [
            {"fact_id": "revenue", "source_id": "fake:source", "value": 120}]},
    })


def test_numerical_accuracy_and_source_validation(example):
    assert score_response(example, example.offline_response)["accuracy"] == 1.0
    fake_source = {"findings": [{"fact_id": "revenue", "value": 120, "source_id": "fake:wrong"}]}
    assert score_response(example, fake_source)["incorrect"] == 1
    hallucination = {"findings": [{"fact_id": "made_up", "value": 999, "source_id": "fake:source"}]}
    assert score_response(example, hallucination)["unsupported"] == 1


def test_bad_json_and_duplicate_findings(example):
    assert score_response(example, "not json")["valid_json"] is False
    duplicate = {"findings": example.offline_response["findings"] * 2}
    assert score_response(example, duplicate)["unsupported"] == 1


def test_reject_nan_and_unverifiable_expected_source(example):
    with pytest.raises(ValueError):
        EvalCase.parse({"case_id": "a",
            "evidence": [{"source_id": "e", "text": "x"}],
            "expected": [{"fact_id": "f", "source_id": "e", "value": float("nan")}]})
    with pytest.raises(ValueError):
        EvalCase.parse({"case_id": "a",
            "evidence": [{"source_id": "e", "text": "x"}],
            "expected": [{"fact_id": "f", "source_id": "invented", "value": 4}]})


@pytest.mark.parametrize("url", [
    "https://localhost:3001/v1",
    "http://example.com:3001/v1",
    "http://localhost.evil.com:3001/v1",
    "http://127.0.0.1/v1",
    "http://username:password@127.0.0.1:3001/v1",
    "http://127.0.0.1:3001/v1?token=a",
])
def test_local_gateway_rejects_external_urls(url):
    with pytest.raises(ValueError):
        LocalGateway("dummy", base_url=url)


def test_error_does_not_expose_prompt_or_token(example):
    def failing_transport(request, timeout):
        raise OSError("secret-token and private user prompt")
    gateway = LocalGateway("secret-token", transport=failing_transport)
    with pytest.raises(GatewayError) as err:
        gateway.chat(messages_for_case(example), "auto")
    assert "secret-token" not in str(err.value)
    assert "private user prompt" not in str(err.value)


def test_exact_payload_and_benchmark(example):
    captured = {}
    def transport(request: Request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data)
        return json.dumps({
            "choices": [{"message": {"content": json.dumps(example.offline_response)}}],
            "model": "demo-provider/test-model",
            "usage": {"prompt_tokens": 30, "completion_tokens": 20},
        }).encode()
    gateway = LocalGateway("dummy", transport=transport)
    row = benchmark([example], ["auto"], gateway)[0]
    assert captured["url"] == "http://127.0.0.1:3001/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer dummy"
    assert captured["payload"]["temperature"] == 0
    assert row["accuracy"] == 1.0
    assert row["actual_model"] == "demo-provider/test-model"
    assert row["prompt_tokens"] == 30


def test_malformed_remote_response(example):
    gateway = LocalGateway("dummy", transport=lambda req, timeout: b"<html>error</html>")
    with pytest.raises(GatewayError):
        gateway.chat(messages_for_case(example), "auto")


def test_live_requires_key_and_model(monkeypatch):
    monkeypatch.delenv("FREELLMAPI_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        main(["--live"])
    with pytest.raises(SystemExit):
        main(["--live", "--model", "auto"])


def test_offline_fixture_and_cli():
    cases = load_cases("examples/llm_eval_synthetic.json")
    assert len(cases) == 1
    assert score_response(cases[0], cases[0].offline_response)["accuracy"] == 1.0
    assert main([]) == 0


def test_redirects_are_explicitly_forbidden():
    from pearl_hunter_quant.llm_lab import _NoRedirect
    handler = _NoRedirect()
    assert handler.redirect_request(None, None, 302, "Found", {}, "http://example.com") is None


def test_local_gateway_fetch_explicitly_disables_proxies(monkeypatch):
    from urllib.request import ProxyHandler
    import pearl_hunter_quant.llm_lab as lab

    captured = {}
    class FakeOpener:
        def open(self, request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            class Response:
                def __enter__(self): return self
                def __exit__(self, *_): return False
                def read(self, size): return b'{"ok": true}'
            return Response()

    def mock_build_opener(*handlers):
        captured["handlers"] = handlers
        return FakeOpener()

    monkeypatch.setattr(lab, "build_opener", mock_build_opener)
    data = lab._fetch(lab.Request("http://127.0.0.1:3001/v1/models"), 2.0)
    assert data == b'{"ok": true}'
    assert captured["url"] == "http://127.0.0.1:3001/v1/models"
    assert captured["timeout"] == 2.0
    assert any(type(h) is ProxyHandler and h.proxies == {} for h in captured["handlers"])
    assert any(isinstance(h, lab._NoRedirect) for h in captured["handlers"])
