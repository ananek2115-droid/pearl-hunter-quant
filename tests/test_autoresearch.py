from datetime import date

import pytest

from pearl_hunter_quant.autoresearch import run_autoresearch


def test_split_is_temporal_and_reproducible():
    rows = [
        {"as_of": "2026-01-01", "signal": 1},
        {"as_of": "2026-01-02", "signal": 1},
        {"as_of": "2026-01-03", "signal": 0},
        {"as_of": "2026-01-04", "signal": 0},
    ]
    result = run_autoresearch(
        rows,
        {"baseline": lambda row: 0.5, "candidate": lambda row: 0.4 if row["signal"] else 0.8},
        train_until=date(2026, 1, 2), validation_until=date(2026, 1, 4),
    )
    assert result.selected == "candidate"
    assert result.to_dict() == run_autoresearch(
        list(reversed(rows)),
        {"baseline": lambda row: 0.5, "candidate": lambda row: 0.4 if row["signal"] else 0.8},
        train_until=date(2026, 1, 2), validation_until=date(2026, 1, 4),
    ).to_dict()
    assert result.real_measurements is False


def test_lookahead_rows_are_rejected():
    with pytest.raises(ValueError, match="outside"):
        run_autoresearch(
            [{"as_of": "2026-01-01"}, {"as_of": "2026-01-05"}],
            {"baseline": lambda row: 0.5},
            train_until=date(2026, 1, 1), validation_until=date(2026, 1, 3),
        )
