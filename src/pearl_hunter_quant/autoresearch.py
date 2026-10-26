"""Small, deterministic autoresearch loop for selector experiments.

The loop is deliberately offline: callers provide dated rows and candidate
scorers. Rows after the training cutoff are never passed to a candidate scorer.
The result is a reproducible experiment log, not a trading recommendation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
from typing import Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Experiment:
    name: str
    train_score: float
    validation_score: float
    complexity: float
    accepted: bool
    reason: str
    dataset_hash: str


@dataclass(frozen=True)
class AutoResearchResult:
    baseline: Experiment
    experiments: tuple[Experiment, ...]
    selected: str
    real_measurements: bool = False
    test_score: float | None = None
    test_until: str | None = None

    def to_dict(self) -> dict:
        return {
            "baseline": asdict(self.baseline),
            "experiments": [asdict(item) for item in self.experiments],
            "selected": self.selected,
            "real_measurements": self.real_measurements,
            "test_score": self.test_score,
            "test_until": self.test_until,
        }


def _hash_rows(rows: Sequence[Mapping[str, object]]) -> str:
    payload = "\n".join(repr(sorted(row.items())) for row in rows)
    return sha256(payload.encode("utf-8")).hexdigest()


def run_autoresearch(
    rows: Iterable[Mapping[str, object]],
    candidates: Mapping[str, Callable[[Mapping[str, object]], float]],
    *,
    train_until: date,
    validation_until: date,
    test_until: date | None = None,
    date_key: str = "as_of",
    complexity: Mapping[str, float] | None = None,
    min_validation_gain: float = 0.0,
) -> AutoResearchResult:
    """Evaluate candidates without lookahead and retain only robust gains.

    Dates must be ISO ``YYYY-MM-DD`` strings. Validation is strictly after the
    training cutoff and at/before ``validation_until``. Candidate names are
    sorted so repeated runs produce the same experiment order.
    If ``test_until`` is supplied, it must be after ``validation_until`` and
    is evaluated exactly once after model selection. It is never used to pick
    a candidate. Without it the result is explicitly not an out-of-sample
    measurement.
    """
    ordered = tuple(sorted((dict(row) for row in rows), key=lambda row: str(row[date_key])))
    if test_until is not None and test_until <= validation_until:
        raise ValueError("test_until must be after validation_until")
    upper = test_until or validation_until
    if any(date.fromisoformat(str(row[date_key])) > upper for row in ordered):
        raise ValueError("rows after validation_until are outside the experiment")
    train = tuple(row for row in ordered if date.fromisoformat(str(row[date_key])) <= train_until)
    validation = tuple(
        row for row in ordered
        if train_until < date.fromisoformat(str(row[date_key])) <= validation_until
    )
    test = tuple(row for row in ordered
                 if test_until is not None
                 and validation_until < date.fromisoformat(str(row[date_key])) <= test_until)
    if not train or not validation:
        raise ValueError("both train and validation cohorts are required")

    costs = complexity or {}
    baseline_name = "baseline"
    if baseline_name not in candidates:
        raise ValueError("candidates must include 'baseline'")

    def score(name: str, cohort: Sequence[Mapping[str, object]]) -> float:
        values = [float(candidates[name](row)) for row in cohort]
        return sum(values) / len(values)

    dataset_hash = _hash_rows(ordered)
    base_train = score(baseline_name, train)
    base_validation = score(baseline_name, validation)
    baseline = Experiment(baseline_name, base_train, base_validation, float(costs.get(baseline_name, 0.0)), True, "baseline", dataset_hash)
    accepted = baseline
    experiments: list[Experiment] = []
    for name in sorted(candidates):
        if name == baseline_name:
            continue
        train_score = score(name, train)
        validation_score = score(name, validation)
        gain = validation_score - accepted.validation_score
        is_accepted = gain >= min_validation_gain and validation_score >= base_validation
        reason = "kept: validation gain" if is_accepted else "discarded: no robust validation gain"
        item = Experiment(name, train_score, validation_score, float(costs.get(name, 0.0)), is_accepted, reason, dataset_hash)
        experiments.append(item)
        if is_accepted and (validation_score, -item.complexity, name) > (accepted.validation_score, -accepted.complexity, accepted.name):
            accepted = item
    test_score = None
    if test_until is not None:
        if not test:
            raise ValueError("test cohort is required when test_until is supplied")
        test_score = score(accepted.name, test)
    return AutoResearchResult(
        baseline, tuple(experiments), accepted.name,
        real_measurements=test_until is not None,
        test_score=test_score,
        test_until=test_until.isoformat() if test_until else None,
    )
