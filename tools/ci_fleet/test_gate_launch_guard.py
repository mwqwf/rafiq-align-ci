import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "index_qa"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_launch_guard as G
import heard_gate as HG

K = "timings-staging/hafs/x.aaaaaaaa.jz"
SHA = "a" * 64
H = {"riwaya": "hafs", "reciterId": "x", "entries": [], "transform": {}}


def test_promoted_already():
    assert "مرقّى" in G.launch_skip_reason(K, H, SHA, {("hafs", "x"): SHA}, "", lambda k: None)
    assert "مرقّى" in G.launch_skip_reason(K, H, SHA, {}, "xx aaaaaaaa", lambda k: None)


def test_base_changed():
    h = dict(H, transform={"fromKey": "timings/hafs/x.jz", "fromSha256": "b" * 64})
    assert "أساسُه" in G.launch_skip_reason(K, h, SHA, {("hafs", "x"): "c" * 64}, "", lambda k: None)
    assert G.launch_skip_reason(K, h, SHA, {("hafs", "x"): "b" * 64}, "", lambda k: None) is None


def test_heard_rejected(monkeypatch=None):
    orig = HG.gate_error
    HG.gate_error = lambda *a: "بوّابةُ السماع: س23 منحرفة"
    try:
        get = lambda k: {"sha256": SHA} if k == HG.state_key(K) else None
        assert "السماع" in G.launch_skip_reason(K, H, SHA, {}, "", get)
        # حكمٌ على بصمةٍ أخرى أو غيابُه لا يمنع
        assert G.launch_skip_reason(K, H, SHA, {}, "", lambda k: {"sha256": "z"}) is None
        assert G.launch_skip_reason(K, H, SHA, {}, "", lambda k: None) is None
    finally:
        HG.gate_error = orig


if __name__ == "__main__":
    test_promoted_already(); test_base_changed(); test_heard_rejected(); print("ok")
