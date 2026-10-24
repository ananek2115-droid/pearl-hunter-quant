"""Research-only opt-in evaluation against a LOCAL FreeLLMAPI gateway."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import time
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener


class GatewayError(RuntimeError):
    """Do not expose auth credentials, provider errors, or prompts."""


@dataclass(frozen=True)
class ChatResult:
    content: str
    actual_model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


def _validate_local_url(base: str) -> str:
    p = urlsplit(base)
    if (p.scheme != "http" or p.hostname not in {"127.0.0.1", "localhost", "::1"}
            or p.username is not None or p.password is not None
            or p.query or p.fragment or p.path.rstrip("/") != "/v1"):
        raise ValueError("Only loopback HTTP FreeLLMAPI /v1 endpoints permitted")
    if p.port is None or not 1 <= p.port <= 65535:
        raise ValueError("Gateway URL requires a valid explicit port")
    return base.rstrip("/")


class _NoRedirect(HTTPRedirectHandler):
    """No redirected prompts or bearer tokens to unexpected destinations."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(request: Request, timeout: float) -> bytes:
    # An explicit empty ProxyHandler prevents ambient HTTP(S)_PROXY values
    # from proxying local prompts; a blocked redirect prevents exfiltration.
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        return response.read(1_000_001)


class LocalGateway:
    def __init__(self, key: str, *, base_url: str = "http://127.0.0.1:3001/v1",
                 timeout: float = 30.0, transport: Callable = _fetch):
        self.base_url = _validate_local_url(base_url)
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Gateway key is required in live mode")
        if not 0 < timeout <= 120:
            raise ValueError("Invalid timeout")
        self._key, self.timeout, self.transport = key, timeout, transport

    def chat(self, messages: list[dict[str, str]], model: str) -> ChatResult:
        if not isinstance(model, str) or not 0 < len(model) <= 200:
            raise ValueError("Explicit model ID required")
        if (not isinstance(messages, list) or not messages
                or any(not isinstance(m, dict)
                       or m.get("role") not in {"system", "user"}
                       or not isinstance(m.get("content"), str) for m in messages)):
            raise ValueError("Only system/user text messages accepted")
        payload = json.dumps({"model": model, "messages": messages,
                              "temperature": 0, "max_tokens": 512},
                             ensure_ascii=False).encode("utf-8")
        if len(payload) > 80_000:
            raise ValueError("Oversized prompt")
        request = Request(
            self.base_url + "/chat/completions", data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self._key}, method="POST")
        start = time.monotonic()
        try:
            raw = self.transport(request, self.timeout)
        except Exception:
            raise GatewayError("Gateway request failed: check connection, authentication and quotas") from None
        elapsed = round((time.monotonic() - start) * 1000)
        if not isinstance(raw, bytes) or len(raw) > 1_000_000:
            raise GatewayError("Invalid or oversized gateway response")
        try:
            response = json.loads(raw)
            content = response["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError()
            usage = response.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}
            def count(field):
                n = usage.get(field)
                return n if type(n) is int and n >= 0 else None
            selected = response.get("model")
            if not isinstance(selected, str):
                selected = ""
        except (ValueError, TypeError, KeyError, IndexError):
            raise GatewayError("Gateway returned malformed chat payload") from None
        return ChatResult(content, selected, count("prompt_tokens"),
                          count("completion_tokens"), elapsed)


def _number(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Expected a numeric fact")
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Non-finite number")
        return number
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid numeric fact") from None


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    evidence: tuple[dict, ...]
    expected: tuple[dict, ...]
    offline_response: dict | None = None

    @classmethod
    def parse(cls, data: dict) -> "EvalCase":
        if not isinstance(data, dict) or not isinstance(data.get("case_id"), str):
            raise ValueError("Case ID required")
        evidence, expected = data.get("evidence"), data.get("expected")
        if not isinstance(evidence, list) or not evidence or not isinstance(expected, list) or not expected:
            raise ValueError("Nonempty evidence and expected arrays required")
        source_ids = set()
        for e in evidence:
            if (not isinstance(e, dict) or not isinstance(e.get("source_id"), str)
                    or not e["source_id"] or not isinstance(e.get("text"), str)
                    or not e["text"] or len(e["text"]) > 4000 or e["source_id"] in source_ids):
                raise ValueError("Bad evidence or duplicate source")
            source_ids.add(e["source_id"])
        fact_ids = set()
        for f in expected:
            if (not isinstance(f, dict) or not isinstance(f.get("fact_id"), str)
                    or not f["fact_id"] or f["fact_id"] in fact_ids
                    or f.get("source_id") not in source_ids):
                raise ValueError("Bad expected fact")
            _number(f.get("value"))
            fact_ids.add(f["fact_id"])
        offline = data.get("offline_response")
        if offline is not None and not isinstance(offline, dict):
            raise ValueError("Bad offline response")
        return cls(data["case_id"], tuple(evidence), tuple(expected), offline)


def messages_for_case(case: EvalCase) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": (
            "Extract only directly reported numeric facts. Return ONLY a JSON "
            "object containing findings, a list of {fact_id, value, source_id}. "
            "Use only requested IDs and exact evidence source IDs. Omit unknowns. "
            "No predictions, investment advice, or invented numbers.")},
        {"role": "user", "content": json.dumps({
            "requested_fact_ids": [e["fact_id"] for e in case.expected],
            "evidence": case.evidence,
        }, ensure_ascii=False)},
    ]


def score_response(case: EvalCase, reply: str | dict) -> dict:
    try:
        data = json.loads(reply) if isinstance(reply, str) else reply
        findings = data["findings"]
        if not isinstance(findings, list) or len(findings) > 50:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        return {"valid_json": False, "exact": 0, "incorrect": 0, "unsupported": 0,
                "missing": len(case.expected), "expected": len(case.expected), "accuracy": 0.0}
    reference = {x["fact_id"]: x for x in case.expected}
    seen = set()
    exact = incorrect = unsupported = 0
    for f in findings:
        if not isinstance(f, dict) or not isinstance(f.get("fact_id"), str):
            unsupported += 1
            continue
        fid = f["fact_id"]
        if fid not in reference or fid in seen:
            unsupported += 1
            continue
        seen.add(fid)
        try:
            valid = (_number(f.get("value")) == _number(reference[fid]["value"])
                     and f.get("source_id") == reference[fid]["source_id"])
        except ValueError:
            valid = False
        if valid:
            exact += 1
        else:
            incorrect += 1
    return {"valid_json": True, "exact": exact, "incorrect": incorrect,
            "unsupported": unsupported, "missing": len(reference) - len(seen),
            "expected": len(reference), "accuracy": round(exact / len(reference), 4)}


def load_cases(path: str | Path) -> list[EvalCase]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or not isinstance(obj.get("cases"), list):
        raise ValueError("Fixture must contain cases")
    cases = [EvalCase.parse(c) for c in obj["cases"]]
    if not cases or len({c.case_id for c in cases}) != len(cases):
        raise ValueError("Cases must have unique, nonempty IDs")
    return cases


def benchmark(cases: list[EvalCase], models: list[str], gateway: LocalGateway) -> list[dict]:
    results = []
    for model in models:
        for case in cases:
            row = {"case_id": case.case_id, "requested_model": model}
            try:
                response = gateway.chat(messages_for_case(case), model)
                row.update(score_response(case, response.content))
                row.update(actual_model=response.actual_model,
                           prompt_tokens=response.prompt_tokens,
                           completion_tokens=response.completion_tokens,
                           latency_ms=response.latency_ms)
            except GatewayError as exc:
                row["error"] = str(exc)
            results.append(row)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Optional local LLM research benchmark")
    parser.add_argument("--fixture", default="examples/llm_eval_synthetic.json")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--base-url", default="http://127.0.0.1:3001/v1")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    cases = load_cases(args.fixture)
    if args.live:
        if not args.model:
            parser.error("--live requires --model at least once")
        key = os.environ.get("FREELLMAPI_API_KEY")
        if not key:
            parser.error("Set FREELLMAPI_API_KEY in your local shell, not in Git")
        gateway = LocalGateway(key, base_url=args.base_url)
        report = {"mode": "live", "results": benchmark(cases, args.model, gateway),
                  "note": "Research experiment, not a validated financial recommendation"}
    else:
        report = {"mode": "offline_fixture_only", "results": [
            {"case_id": c.case_id, **score_response(c, c.offline_response)}
            if c.offline_response else {"case_id": c.case_id, "error": "Missing offline response"}
            for c in cases],
            "note": "Offline fixtures do NOT benchmark a real model"}
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
