"""Point-in-time feature validation for prospective research.

Every feature must declare when its source became public and when it was
available to the research process. The validator is intentionally offline.
It prevents a correctly dated signal from hiding a future-dated input.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Sequence


def _stamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid timestamp") from None
    if result.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return result.astimezone(timezone.utc)


def validate_features(rows: Sequence[Mapping[str, object]], *, as_of: str) -> list[dict[str, object]]:
    """Return normalized features, rejecting unavailable or ambiguous inputs."""
    cutoff = _stamp(as_of)
    result: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("feature row must be an object")
        ticker, name = row.get("ticker"), row.get("feature")
        if not isinstance(ticker, str) or not ticker or not isinstance(name, str) or not name:
            raise ValueError("feature needs ticker and name")
        public_at = _stamp(row.get("source_public_at_utc"))
        available_at = _stamp(row.get("available_at_utc"))
        if public_at > available_at or available_at > cutoff:
            raise ValueError("feature was not available at the research cutoff")
        key = (ticker, name)
        if key in seen:
            raise ValueError("duplicate feature")
        seen.add(key)
        result.append({
            "ticker": ticker,
            "feature": name,
            "value": row.get("value"),
            "source_public_at_utc": public_at.isoformat(),
            "available_at_utc": available_at.isoformat(),
            "source_id": row.get("source_id"),
        })
    return result
