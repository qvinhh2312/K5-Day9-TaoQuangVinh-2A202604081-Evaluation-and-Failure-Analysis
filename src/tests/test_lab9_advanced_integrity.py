"""Extra M5/M7 checks for traps the public tests do not build (hidden-grader style)."""
import copy

import pytest

pytestmark = pytest.mark.student

ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["denial"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2",
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "denial", "metric": "pass_rate", "min": 0.9, "no_significant_drop": True, "blocking": True}]}


def _report(rows, metrics=None, seeds=(1, 2), items=4):
    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)}, "rows": rows,
            "metrics": metrics or {"pass_rate": 1.0}, "evaluator_failures": []}


@pytest.fixture()
def gate():
    from lab9 import gate
    return gate


def test_baseline_against_itself_is_clean(gate):
    base = _report(copy.deepcopy(ROWS))
    assert gate.integrity_check(base, base, SPEC, SPEC) == []


def test_duplicate_row_cannot_replace_a_dropped_one(gate):
    base = _report(copy.deepcopy(ROWS))
    rows = copy.deepcopy(ROWS[:-1]) + [copy.deepcopy(ROWS[0])]      # right count, wrong grid
    assert gate.integrity_check(_report(rows), base, SPEC)


def test_evaluator_failures_and_none_values(gate):
    base = _report(copy.deepcopy(ROWS))
    failed = _report(copy.deepcopy(ROWS)); failed["evaluator_failures"] = ["E-001@1:TrialPass:boom"]
    assert gate.integrity_check(failed, base, SPEC)
    rows = copy.deepcopy(ROWS); rows[3]["pass_rate"] = None
    assert gate.integrity_check(_report(rows), base, SPEC)


def test_relabelled_slice_is_flagged(gate):
    base = _report(copy.deepcopy(ROWS))
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if r["item_id"] == "E-000":
            r["slices"] = []
    assert gate.integrity_check(_report(rows), base, SPEC)


def test_hand_edited_metric_is_flagged(gate):
    base = _report(copy.deepcopy(ROWS))
    rows = copy.deepcopy(ROWS); rows[0]["pass_rate"] = False
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base, SPEC)


def test_manifest_seeds_must_match_baseline(gate):
    base = _report(copy.deepcopy(ROWS))
    pr = _report([r for r in copy.deepcopy(ROWS) if r["seed"] == 1], seeds=(1,))
    assert gate.integrity_check(pr, base, SPEC)


@pytest.mark.parametrize("edit", ["drop_slice", "lower_min", "non_blocking", "drop_drop", "drop_metric"])
def test_ratchet_catches_every_loosening(gate, edit):
    base = _report(copy.deepcopy(ROWS))
    loose = copy.deepcopy(SPEC)
    if edit == "drop_slice":
        loose["slices"] = []
    elif edit == "lower_min":
        loose["slices"][0]["min"] = 0.5
    elif edit == "non_blocking":
        loose["slices"][0]["blocking"] = False
    elif edit == "drop_drop":
        loose["metrics"][0]["threshold"].pop("no_significant_drop")
    else:
        loose["metrics"] = []
    assert gate.integrity_check(base, base, loose, SPEC)


def test_stricter_spec_and_new_version_are_allowed(gate):
    base = _report(copy.deepcopy(ROWS))
    strict = copy.deepcopy(SPEC); strict["metrics"][0]["threshold"]["min"] = 0.9
    assert gate.integrity_check(base, base, strict, SPEC) == []
    other = dict(copy.deepcopy(SPEC), eval_set_version="v3", slices=[])
    assert gate.integrity_check(base, base, other, SPEC) == []


def test_empty_slice_is_blocked(gate):
    base = _report(copy.deepcopy(ROWS))
    spec = dict(SPEC, slices=[{"name": "ghost", "metric": "pass_rate", "blocking": True}])
    blocked, _ = gate.slice_check(base, base, spec)
    assert blocked == ["slice:ghost/pass_rate"]


def test_non_blocking_slice_is_only_a_warning(gate):
    base = _report(copy.deepcopy(ROWS))
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if "denial" in r["slices"]:
            r["pass_rate"] = False
    spec = dict(SPEC, slices=[{"name": "denial", "metric": "pass_rate", "min": 0.9, "blocking": False}])
    blocked, lines = gate.slice_check(_report(rows), base, spec)
    assert blocked == [] and "warn" in lines[0]
