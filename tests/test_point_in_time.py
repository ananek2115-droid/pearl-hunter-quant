import pytest

from pearl_hunter_quant.point_in_time import validate_features


def test_features_must_be_available_before_cutoff():
    rows = [{
        "ticker": "ABC", "feature": "revenue", "value": 10,
        "source_public_at_utc": "2026-01-01T10:00:00Z",
        "available_at_utc": "2026-01-01T10:05:00Z", "source_id": "filing-1",
    }]
    assert validate_features(rows, as_of="2026-01-01T12:00:00Z")[0]["ticker"] == "ABC"


def test_future_feature_is_rejected():
    with pytest.raises(ValueError, match="available"):
        validate_features([{
            "ticker": "ABC", "feature": "revenue", "value": 10,
            "source_public_at_utc": "2026-01-01T10:00:00Z",
            "available_at_utc": "2026-01-02T10:00:00Z",
        }], as_of="2026-01-01T12:00:00Z")
