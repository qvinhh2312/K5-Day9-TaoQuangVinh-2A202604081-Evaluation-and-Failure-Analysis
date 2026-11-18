"""RefundAmountCorrect also compares the proposal, so a wrong proposal behind a correct ledger is caught."""
import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 0, "proposal_amount": 35000}


def _ctx(trial, label=LABEL):
    from pydantic_evals.evaluators import EvaluatorContext
    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def _trial(proposal, refund_vnd=0):
    return {"snapshot": {"refund_vnd": refund_vnd, "refund_count": 0}, "unexpected_rows": 0, "blob": "",
            "events": [], "result": {"proposal_amount": proposal}, "lab8_pass": True, "lab8_reason": None}


def test_wrong_proposal_with_correct_ledger_is_flagged():
    from lab9.graders import RefundAmountCorrect
    res = RefundAmountCorrect().evaluate(_ctx(_trial(0)))
    assert res.value is False and "proposal 0" in res.reason


def test_matching_proposal_and_ledger_passes():
    from lab9.graders import RefundAmountCorrect
    assert RefundAmountCorrect().evaluate(_ctx(_trial(35000))).value is True


def test_missing_proposal_on_either_side_is_ignored():
    from lab9.graders import RefundAmountCorrect
    t = _trial(35000); t["result"] = {}
    assert RefundAmountCorrect().evaluate(_ctx(t)).value is True
    assert RefundAmountCorrect().evaluate(_ctx(_trial(0), {"refund_vnd": 0})).value is True
