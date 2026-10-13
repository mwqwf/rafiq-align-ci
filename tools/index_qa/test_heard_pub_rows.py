# -*- coding: utf-8 -*-
"""اختبار وضع --sweep في heard_pub_rows (pV · 2026-10-13): الحكمُ على الفهرس الحيّ لا المقيس،
وكشفُ القياس المتقادم، وكشفُ التمدّد الزمنيّ."""
import sys, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules.setdefault("run", types.SimpleNamespace(s3=None))
import heard_pub_rows as R  # noqa: E402


def _idx(starts, sha="A"):
    return {"entries": [{"ayahId": f"2:{a}", "startMs": st, "endMs": st + 1000} for a, st in starts.items()],
            "audioSha256": [None, sha] + [None] * 112}


def _rep(anchors, idx_sha="X", sha="A"):
    return {"sha256": idx_sha, "maps": {"2": {"sha256": sha, "anchors": {str(a): [[t, t + 900], 0.95, []]
                                                                         for a, t in anchors.items()}}}}


def test_live_index_agrees_stale_measure_flagged():
    starts = {a: a * 100000 for a in range(1, 21)}
    line = R.sweep_line("timings/hafs/x.jz", _idx(starts), "LIVE0000", _rep(starts, idx_sha="OLD00000"))
    assert "متقادم(OLD00000)" in line and "منحرفة=0" in line and "تمدّد=-" in line


def test_stretch_detected():
    starts = {a: a * 100000 for a in range(1, 21)}
    heard = {a: int(t * 3.6) for a, t in starts.items()}
    line = R.sweep_line("timings/qalun/y.jz", _idx(starts), "LIVE", _rep(heard, idx_sha="LIVE"))
    assert "\tحيّ\t" in line and "2×3.6" in line and "منحرفة=20" in line


def test_audio_mismatch_not_judged():
    starts = {a: a * 100000 for a in range(1, 21)}
    heard = {a: t + 9000 for a, t in starts.items()}
    line = R.sweep_line("k", _idx(starts, sha="A"), "L", _rep(heard, sha="B"))
    assert "صوت≠=1" in line and "منحرفة=0" in line


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("✓", n)
