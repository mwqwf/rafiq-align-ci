"""حجزُ المرشّح بعينه: مفتاحُ `timings-staging/<ر>/<م>.<بصمة8>.jz` يحجب تلك البصمة وحدها."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promote  # noqa: E402


def _held(text):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "hold.txt"
        p.write_text(text, encoding="utf-8")
        old = promote.HOLD
        promote.HOLD = p
        try:
            return promote.held()
        finally:
            promote.HOLD = old


def _rep(sha8):
    return {"key": f"timings-staging/hafs/nasser_almajed.{sha8}.jz",
            "riwaya": "hafs", "reciterId": "nasser_almajed", "verdict": "x"}


def test_candidate_hold_blocks_only_that_sha():
    holds = _held("timings-staging/hafs/nasser_almajed.05b18814.jz\tسبب\n")
    _t, why = promote.gate(_rep("05b18814"), {}, "", holds)
    assert why.startswith("محجوز")
    _t, why = promote.gate(_rep("1e1b3eed"), {}, "", holds)
    assert not why.startswith("محجوز")


def test_target_hold_still_blocks_every_candidate():
    holds = _held("timings/hafs/nasser_almajed.jz\tسبب\n")
    for sha in ("05b18814", "1e1b3eed"):
        _t, why = promote.gate(_rep(sha), {}, "", holds)
        assert why.startswith("محجوز")


def test_sampling_skip_honours_candidate_hold():
    holds = _held("timings-staging/hafs/nasser_almajed.05b18814.jz\tسبب\n")
    assert promote.sampling_skip_reason(_rep("05b18814")["key"], [], holds) == "محجوز"
    assert promote.sampling_skip_reason(_rep("1e1b3eed")["key"], [], holds) is None


def test_malformed_key_still_warned(capsys):
    _held("timings-staging/hafs/nasser_almajed.jz\tسبب\n")
    assert "لا تحجب شيئاً" in capsys.readouterr().err
