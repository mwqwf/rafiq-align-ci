"""اختبارات تعديلين ضيّقين في promote: رفع التعارض لإسقاطٍ معتمد، وسماح النقص المعتمد بنصّ المالك."""
import gzip
import io
import json

import pytest

from tools.index_qa import promote as P

PFX = P.DROP_DECISION_PREFIX
KEY = "timings-staging/hafs/x.y.jz"
APP = {KEY: frozenset({4})}


@pytest.fixture(autouse=True)
def _no_withdrawn(monkeypatch):
    monkeypatch.setattr(P, "WITHDRAWN_MAP", {})


def _rep(src="s", hi=0.02, drops=(4,), verdict=None, sha="a" * 64):
    dec = [f"{PFX}: {list(drops)} (السبب: x) — قرارُ منتَجٍ يُعرض على المشرف، لا حكمُ جودة"]
    r = {"key": KEY, "reciterId": "y", "riwaya": "hafs", "source": src, "engine": "e1",
         "verdict": verdict or ("موقوف — قرارُ منتَجٍ مطلوب: " + dec[0]),
         "fatal": [], "decision": dec, "declaredDrops": sorted(drops), "ts": 1, "sha256": sha,
         "sample": {"seed": 1, "seedSalt": "s1", "severe": [2, 300, [2 / 300, 0.0, hi]]},
         "severeRate": {"rate": 0.007, "lo": None, "hi": hi}}
    return r


def _gate(rep, ci, pooled, approvals=APP):
    return P.gate(rep, set(), "", {}, None, {rep["sha256"]: ci} if ci else None, None,
                  {rep["sha256"]: pooled} if pooled else None, approvals)[1]


def test_conflict_lifted_when_all_three_approved_and_hi_below_ceiling():
    assert _gate(_rep(), _rep("ci", hi=0.08), _rep("pooled", hi=0.04)) is None


def test_conflict_without_approval_refused():
    why = _gate(_rep(), _rep("ci", hi=0.08), _rep("pooled", hi=0.04), {})
    assert why


def test_conflict_pooled_hi_at_ceiling_refused():
    why = _gate(_rep(), _rep("ci", hi=0.08), _rep("pooled", hi=P.SEVERE_CEILING))
    assert why and "تعارض" in why


def test_conflict_pooled_hi_above_ceiling_refused():
    assert _gate(_rep(), _rep("ci", hi=0.08), _rep("pooled", hi=0.07))


def test_conflict_declared_drops_differ_refused():
    assert _gate(_rep(), _rep("ci", hi=0.08, drops=(4, 5)), _rep("pooled", hi=0.04))


def test_conflict_ci_not_an_approved_drop_refused():
    ci = _rep("ci", hi=0.08, verdict="مرفوض — عطب")
    assert _gate(_rep(), ci, _rep("pooled", hi=0.04))


def test_conflict_no_pooled_refused():
    assert _gate(_rep(), _rep("ci", hi=0.08), None)


def test_conflict_pooled_hi_not_number_refused():
    p = _rep("pooled")
    p["severeRate"] = {"rate": 0.01, "hi": None}
    assert _gate(_rep(), _rep("ci", hi=0.08), p)


# ---- النقص ----
T = "timings/hafs/y.jz"
A = _AYAH = P._AYAH_COUNTS


class _Cl:
    def __init__(self, ids):
        self.ids = ids

    def get_object(self, **_kw):
        body = gzip.compress(json.dumps(
            {"entries": [{"ayahId": i} for i in self.ids]}).encode())
        return {"Body": io.BytesIO(body)}


def _all():
    return [f"{s}:{a}" for s in range(1, 115) for a in range(1, A[s - 1] + 1)]


def _file(tmp_path, rows):
    p = tmp_path / "ap.json"
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return p


def _row(ayahs, key=KEY, att=("محاولة",), ref="قاعدة"):
    return {"key": key, "ayahs": ayahs, "rule_ref": ref, "attempts": list(att)}


def _shrink(tmp_path, rows, lost, key=KEY):
    old = _all()
    new = [i for i in old if i not in set(lost)]
    return P.shrink_refusal(_Cl(old), "b", T, len(new), new_ids=new, key=key,
                            approvals_path=_file(tmp_path, rows))


def test_shrink_tail_ayah_approved(tmp_path):
    assert _shrink(tmp_path, [_row(["69:52"])], ["69:52"]) is None


def test_shrink_head_ayahs_approved(tmp_path):
    assert _shrink(tmp_path, [_row(["9:1", "9:2"])], ["9:1", "9:2"]) is None


def test_shrink_middle_ayah_refused(tmp_path):
    assert _shrink(tmp_path, [_row(["69:20"])], ["69:20"])


def test_shrink_disconnected_ayahs_refused(tmp_path):
    rows = [_row(["69:50", "69:52"])]
    assert _shrink(tmp_path, rows, ["69:50", "69:52"])


def test_shrink_no_attempts_refused(tmp_path):
    assert _shrink(tmp_path, [_row(["69:52"], att=())], ["69:52"])


def test_shrink_blank_rule_ref_refused(tmp_path):
    assert _shrink(tmp_path, [_row(["69:52"], ref=" ")], ["69:52"])


def test_shrink_other_key_refused(tmp_path):
    assert _shrink(tmp_path, [_row(["69:52"], key="other.jz")], ["69:52"])


def test_shrink_whole_surah_as_ayahs_refused(tmp_path):
    ids = [f"112:{a}" for a in range(1, 5)]
    assert _shrink(tmp_path, [_row(ids)], ids)


def test_shrink_extra_lost_beyond_approval_refused(tmp_path):
    assert _shrink(tmp_path, [_row(["69:52"])], ["69:52", "69:51"])


def test_shrink_approved_surah_drop(tmp_path):
    rows = [{"key": KEY, "surahs": [4], "rule_ref": "ق", "attempts": ["م"]}]
    lost = [f"4:{a}" for a in range(1, 177)]
    assert _shrink(tmp_path, rows, lost) is None


def test_shrink_surah_drop_plus_other_surah_refused(tmp_path):
    rows = [{"key": KEY, "surahs": [4], "rule_ref": "ق", "attempts": ["م"]}]
    lost = [f"4:{a}" for a in range(1, 177)] + ["5:1"]
    assert _shrink(tmp_path, rows, lost)


def test_shrink_without_new_ids_still_refused(tmp_path):
    old = _all()
    why = P.shrink_refusal(_Cl(old), "b", T, len(old) - 1)
    assert why and "allow-shrink" in why


def test_shrink_no_approval_file_refused(tmp_path):
    assert _shrink(tmp_path, [], ["69:52"])
