"""Unit tests for FM-08 grader: ReplyAmountMatchesLedger."""
import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 35000, "approval_ok": True}


@pytest.fixture(scope="module")
def grader():
    from lab9.graders import ReplyAmountMatchesLedger
    return ReplyAmountMatchesLedger()


def ctx(trial, label=LABEL):
    from pydantic_evals.evaluators import EvaluatorContext
    return EvaluatorContext(
        name="t", inputs={}, metadata=None, expected_output=label, output=trial,
        duration=0.0, _span_tree=None, attributes={}, metrics={}
    )


def trial(refund_vnd=35000, text=None, events=None):
    if events is None:
        events = [{"kind": "reply", "payload": {"text": text}}] if text is not None else []
    return {
        "snapshot": {"refund_vnd": refund_vnd, "refund_count": 1 if refund_vnd > 0 else 0},
        "unexpected_rows": 0, "blob": "", "events": events,
        "result": {}, "lab8_pass": True, "lab8_reason": None,
    }


def test_matching_reply_and_ledger(grader):
    t = trial(refund_vnd=35000, text="Dạ, LogiX đã hoàn 35.000đ cho đơn O-107.")
    res = grader.evaluate(ctx(t))
    assert res.value is True


def test_mismatched_amount_in_reply(grader):
    t = trial(refund_vnd=20000, text="Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.")
    res = grader.evaluate(ctx(t))
    assert res.value is False
    assert "reply [35000] vs ledger 20000" in (res.reason or "")


def test_paraphrase_matching(grader):
    t = trial(refund_vnd=35000, text="LogiX đã hoàn phí 35.000đ cho đơn O-107 của anh/chị ạ.")
    res = grader.evaluate(ctx(t))
    assert res.value is True


def test_currency_formats(grader):
    formats = [
        "Đã hoàn 35.000đ",
        "Đã hoàn 35,000 đ",
        "Đã hoàn 35000vnđ",
        "Đã hoàn 35.000 đồng",
        "Đã hoàn 35000 ₫",
    ]
    for text in formats:
        t = trial(refund_vnd=35000, text=text)
        assert grader.evaluate(ctx(t)).value is True, f"Failed on {text}"


def test_reply_only_order_id_no_money(grader):
    t = trial(refund_vnd=0, text="Dạ, đơn O-112 chưa đủ điều kiện hoàn theo chính sách hiện hành.")
    res = grader.evaluate(ctx(t))
    assert res.value is True


def test_escalated_or_needs_info_no_money(grader):
    t = trial(refund_vnd=0, text="Dạ, yêu cầu đã được chuyển cho chuyên viên xử lý.")
    res = grader.evaluate(ctx(t))
    assert res.value is True


def test_empty_events(grader):
    t = trial(refund_vnd=0, events=[])
    res = grader.evaluate(ctx(t))
    assert res.value is True


def test_ledger_zero_but_reply_claims_refund(grader):
    t = trial(refund_vnd=0, text="Dạ, LogiX đã hoàn 50.000đ cho đơn O-909.")
    res = grader.evaluate(ctx(t))
    assert res.value is False
    assert "reply [50000] vs ledger 0" in (res.reason or "")


def test_misreport_variant_reply_is_caught_and_fixed_is_clean(grader):
    from lab8.shapes import SHAPES
    from lab9 import variants
    from lab9.trace_case import investigate
    from lab9.variant_agent import make_shape
    variants.register()
    SHAPES.setdefault("tmp_fm08", make_shape("tmp_fm08", {"no_override", "misreport"}))
    bad = investigate("tmp_fm08", "C-008", 11)
    assert grader.evaluate(ctx(bad["trial"], bad["label"])).value is False
    ok = investigate("fixed", "C-008", 11)
    assert grader.evaluate(ctx(ok["trial"], ok["label"])).value is True
