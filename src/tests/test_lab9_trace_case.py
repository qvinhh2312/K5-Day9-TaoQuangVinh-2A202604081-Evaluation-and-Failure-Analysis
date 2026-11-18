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

