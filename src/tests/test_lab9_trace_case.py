import pytest
from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def test_c002_seeded_regression_fails_and_fixed_passes():
    bad_trial = investigate("seeded_regression", "C-002", 11)["trial"]
    fixed_trial = investigate("fixed", "C-002", 11)["trial"]

    # seeded_regression violates ground truth (FM-03: ticket_trust leads to illegal refund)
    assert bad_trial["lab8_pass"] is False, "seeded_regression should fail on C-002@11"
    assert bad_trial["snapshot"]["refund_vnd"] > 0, "seeded_regression issued unwanted refund"
    assert any(e.get("kind") == "model_override" for e in bad_trial["events"]), "missing model_override event"

    # fixed passes with 0 refund
    assert fixed_trial["lab8_pass"] is True, "fixed should pass on C-002@11"
    assert fixed_trial["snapshot"]["refund_vnd"] == 0, "fixed should not issue refund"
    assert fixed_trial["result"]["status"] == "denied"



def _ctx(trial, label):
    from pydantic_evals.evaluators import EvaluatorContext
    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def test_c002_lab9_graders_catch_the_override_and_the_wrong_refund():
    from lab9.graders import DbFactKept, RefundAmountCorrect
    from lab9.trace_case import investigate as inv
    bad, fixed = inv("seeded_regression", "C-002", 11), inv("fixed", "C-002", 11)
    label = bad["label"]
    # first wrong step is event 3 (model_override), before any quote or refund exists
    assert bad["trial"]["events"][2]["kind"] == "model_override"
    assert DbFactKept().evaluate(_ctx(bad["trial"], label)).value is False
    assert RefundAmountCorrect().evaluate(_ctx(bad["trial"], label)).value is False
    assert DbFactKept().evaluate(_ctx(fixed["trial"], label)).value is True
    assert RefundAmountCorrect().evaluate(_ctx(fixed["trial"], label)).value is True
