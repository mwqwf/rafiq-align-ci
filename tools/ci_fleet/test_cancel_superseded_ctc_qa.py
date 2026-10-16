# -*- coding: utf-8 -*-
"""اختبارُ إلغاء أحكام السائق المنتظرة على المرشّحات المتجاوَزة."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cancel_superseded_ctc_qa import run_key, superseded  # noqa: E402

K_OLD = "timings-staging/hafs/nabil.410d1286.jz"
K_NEW = "timings-staging/hafs/nabil.aaaaaaaa.jz"
QA = ".github/workflows/audio_qa.yml"
OP = ".github/workflows/openers.yml"


def r(title, path=QA, status="queued", event="workflow_dispatch"):
    return {"display_title": title, "path": path, "status": status, "event": event}


def test_run_key_driver_qa():
    assert run_key(r(f"qa {K_OLD} · salt=k3 · n=20")) == K_OLD


def test_run_key_driver_openers():
    assert run_key(r(f"openers {K_OLD} · n=1", OP)) == K_OLD


def test_run_key_refuses_manual_salt_running_and_other_paths():
    assert run_key(r(f"qa {K_OLD} · salt=e1hd2 · n=20")) is None
    assert run_key(r(f"qa {K_OLD} · salt=k1 · n=20", status="in_progress")) is None
    assert run_key(r(f"qa {K_OLD} · salt=k1 · n=20", path=OP)) is None
    assert run_key(r(f"openers {K_OLD} · n=8", OP)) is None
    assert run_key(r(f"qa timings/hafs/nabil.jz · salt=k1 · n=20")) is None
    assert run_key(r(f"qa {K_OLD} · salt=k1 · n=20", event="schedule")) is None


def test_superseded_only_by_newer_same_reciter():
    staged = {K_OLD: 100.0, K_NEW: 200.0, "timings-staging/warsh/nabil.bbbbbbbb.jz": 300.0}
    assert superseded(K_OLD, staged)
    assert not superseded(K_NEW, staged)
    assert not superseded(K_OLD, {K_OLD: 100.0, "timings-staging/hafs/sayed.cccccccc.jz": 300.0})
    assert not superseded("timings-staging/hafs/x.dddddddd.jz", staged)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
