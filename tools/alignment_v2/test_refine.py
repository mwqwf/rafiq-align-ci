# -*- coding: utf-8 -*-
"""اختبارات منطق الصقل بلا whisper (حقن clip_words) — python test_refine.py"""
import refine


def _case(hyp_words, sil, seg_end=6000, snapped=False):
    ref = ["الحمد لله رب العالمين", "الرحمن الرحيم"]
    entries = [
        {"ayahIdx": 0, "startMs": 0, "endMs": 3000, "conf": 0.8, "snapped": True,
         "matched": 4, "total": 4},
        {"ayahIdx": 1, "startMs": 3000, "endMs": seg_end, "conf": 0.5, "snapped": snapped,
         "matched": 2, "total": 2},
    ]
    refine.clip_words = lambda *a, **k: hyp_words
    refine.silences = lambda *a, **k: sil
    d = {"surah": 1, "segments": [{"s": 0, "e": seg_end, "words": []}],
         "entries": entries, "refAyahs": ref, "wav": "x", "totalMs": seg_end}
    refine.refine_surah(d, log=lambda *_: None)
    return entries, d["refineStats"]


FULL = [{"w": "الحمد", "s": 100, "e": 900}, {"w": "لله", "s": 900, "e": 1700},
        {"w": "رب", "s": 1700, "e": 2400}, {"w": "العالمين", "s": 2400, "e": 3600},
        {"w": "الرحمن", "s": 4200, "e": 5000}, {"w": "الرحيم", "s": 5000, "e": 5800}]


def test_snap_to_silence():
    e, st = _case(FULL, [(3650, 4150)])
    assert e[1]["startMs"] == 3900, e[1]["startMs"]      # مركز الصمت
    assert e[0]["endMs"] == 3900                          # النهاية تلاصق البداية
    assert e[1]["refineSrc"] == "token-snap" and e[1]["conf"] >= 0.75
    assert st == {"targets": 1, "refined": 1, "no_anchor": 0, "no_words": 0,
                  "slid": 0, "edge": 0, "no_silence": 0}


def test_no_silence_is_rejected():
    """⛔ لا صمت لا حد: المنتصف تخمين (مقيس: token-mid صفر من عشرة) ⇒ رفض."""
    e, st = _case(FULL, [])
    assert st["no_silence"] == 1 and not e[1]["refined"]
    assert e[1]["startMs"] == 3000 and e[1]["refineSrc"] == "skip:no-silence"


def test_long_segment_is_still_refined():
    """المقطع الطويل لم يعد عائقاً: النافذة قصيرة مهما طال المقطع (الدرس المقيس)."""
    e, st = _case(FULL, [(3650, 4150)], seg_end=40_000)
    assert st["refined"] == 1 and e[1]["refined"] and e[1]["startMs"] == 3900


def test_no_anchor_leaves_boundary_untouched():
    """كلمات النافذة كلها للآية الأولى ⇒ لا مرساة للاحقة ⇒ لا تغيير."""
    e, st = _case(FULL[:4], [(3650, 4150)])
    assert st["no_anchor"] == 1 and not e[1]["refined"] and e[1]["startMs"] == 3000


def test_one_sided_anchor_is_rejected():
    """مرساة واحدة فقط على أحد الجانبين (< MIN_ANCHOR) ⇒ رفض لا تخمين."""
    hyp = FULL[:4] + [{"w": "الرحمن", "s": 4200, "e": 5000}]
    e, st = _case(hyp, [(3650, 4150)])
    assert st["no_anchor"] == 1 and not e[1]["refined"]


def test_snapped_boundary_is_not_a_target():
    e, st = _case(FULL, [(3650, 4150)], snapped=True)
    assert st["targets"] == 0 and not e[1]["refined"]





def test_guard_blocks_promotion_on_low_accuracy():
    """تطابق ضعيف ⇒ يبقى MED ولو التُقط على صمت."""
    hyp = [dict(w, w="خطأ") if i in (0, 1, 4) else w for i, w in enumerate(FULL)]
    e, _ = _case(hyp, [(3650, 4150)])
    if e[1]["refined"]:
        assert (e[1]["refineAcc"] >= refine.PROMOTE_MIN_ACC) == e[1]["promoted"]
        if not e[1]["promoted"]:
            assert e[1]["conf"] <= refine.MED_CEIL


def test_window_edge_result_is_rejected():
    """حدٌّ يستقر على حافة النافذة = فشل مقنَّع ⇒ يُرفض ولا يُقصّ."""
    hyp = [{"w": "الحمد", "s": 100, "e": 200}, {"w": "لله", "s": 200, "e": 300},
           {"w": "الرحمن", "s": 400, "e": 500}, {"w": "الرحيم", "s": 500, "e": 600}]
    e, st = _case(hyp, [(300, 400)])
    assert st["edge"] == 1 and not e[1]["refined"]
    assert e[1]["startMs"] == 3000 and e[1]["refineSrc"] == "skip:window-edge"


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
            print(f"✅ {k}")
            n += 1
    print(f"{n}/{n} اختبارات خضراء")
