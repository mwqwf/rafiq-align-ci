"""اختبارات مسار «الإسقاط المعتمد»: موقوفٌ لسببٍ واحد (سورٌ أذن المالك بإسقاطها) يمرّ بالحكم،
وتبقى كلُّ الحرّاس الأخرى (فاتل · عيّنة · D-068 · تعارض) سارية."""
import json
import pytest

from tools.index_qa import promote as P

PFX = P.DROP_DECISION_PREFIX
KEY = "timings-staging/hafs/x.y.jz"


def _rep(drops=(38,), hi=0.02, n=300, decision=None, fatal=None, verdict=None, with_field=True):
    dec = [f"{PFX}: {list(drops)} (السبب: x) — قرارُ منتَجٍ يُعرض على المشرف، لا حكمُ جودة"] \
        if decision is None else decision
    r = {"key": KEY, "reciterId": "y", "riwaya": "hafs", "source": "ci", "engine": "e1",
         "verdict": verdict or ("موقوف — قرارُ منتَجٍ مطلوب: " + " · ".join(dec)),
         "fatal": fatal or [], "decision": dec, "ts": 1, "sha256": "a" * 64,
         "sample": {"seed": 1, "seedSalt": "s1", "severe": [2, n, [2 / n, 0.0, hi]]}}
    if with_field:
        r["declaredDrops"] = sorted(drops)
    return r


APP = {KEY: frozenset({38, 39})}


def _gate(rep, approvals=APP):
    # لا ردّ آخر: فتح الشاهد المسحوب وتجاوز المطالع بتعطيلٍ يخصّ الاختبار فقط
    return P.gate(rep, set(), "", {}, None, None, None, None, approvals)


@pytest.fixture(autouse=True)
def _no_withdrawn(monkeypatch):
    monkeypatch.setattr(P, "WITHDRAWN_MAP", {})


def test_no_approval_rejected():
    assert _gate(_rep(), {})[1]


def test_approval_for_fewer_surahs_rejected():
    assert _gate(_rep(drops=(38, 40)), {KEY: frozenset({38})})[1]


def test_non_drop_decision_line_rejected():
    r = _rep(decision=[f"{PFX}: [38] x", "قرارٌ آخر"])
    assert not P.approved_drop(r, APP)
    assert _gate(r)[1]


def test_fatal_rejected():
    assert _gate(_rep(fatal=["خلل"]))[1]


def test_upper_bound_over_5_rejected():
    why = _gate(_rep(hi=0.06))[1]
    assert why and "D-068" in why


def test_valid_with_clean_sample_passes():
    assert _gate(_rep(hi=0.02))[1] is None


def test_missing_declared_drops_field_rejected():
    r = _rep(with_field=False)
    assert not P.approved_drop(r, APP)
    assert _gate(r)[1]


def test_incomplete_approval_rows_ignored(tmp_path):
    good = {"key": "k", "surahs": [1], "rule_ref": "r", "attempts": ["a"]}
    bad = [dict(good, key=""), dict(good, surahs=[0]), dict(good, surahs=[115]),
           dict(good, surahs=[True]), dict(good, surahs=[]), dict(good, rule_ref=" "),
           dict(good, attempts=[]), dict(good, attempts=[""]), "x", {"key": "k"}]
    f = tmp_path / "a.json"
    f.write_text(json.dumps(bad + [good]), encoding="utf-8")
    assert P.load_drop_approvals(f) == {"k": frozenset({1})}
    f.write_text("{تالف", encoding="utf-8")
    assert P.load_drop_approvals(f) == {}
    assert P.load_drop_approvals(tmp_path / "none.json") == {}


def test_pooled_samples_accepts_approved_hold_only():
    a, b = _rep(), _rep()
    b["sample"] = dict(b["sample"], seed=2, seedSalt="s2")
    assert P.pooled_samples([a, b], APP) is not None
    assert P.pooled_samples([a, b], {}) is None
    c = _rep(fatal=["x"], verdict="مرفوض (خلل بنيوي)")
    c["sample"] = dict(c["sample"], seed=3, seedSalt="s3")
    assert P.pooled_samples([a, b, c], APP) is None
