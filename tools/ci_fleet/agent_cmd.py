#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ناقلُ أوامرِ الوكيل السحابيّ — يُنفَّذ داخل العدّاء بصلاحيّاته لا بصلاحيّات الوكيل.

**المشكلةُ التي يحلّها (مقيسةٌ لا مظنونة):** جلسةُ كلود السحابيّة تقرأ جيت هَب
ولا تملك `workflow_dispatch` (‏`403`)، ولا تملك اعتمادَ الدلو. فكانت عاجزةً عن
ثلاثةِ أشياءَ هي صُلبُ العمل: **إطلاقُ محاذاة · القياسُ من الدلو · الترقية**.

**الحلّ:** الوكيلُ يكتب أمراً في `ops/commands/<اسم>.json` ويدفعه، فيستيقظ
`agent_cmd.yml` وينفّذه **بصلاحيّاته هو** ثمّ يُعيد الجواب إلى `ops/out/`.
⭐ **فالصلاحيةُ تبقى حيث هي، والأمرُ يُنقل إليها** — ولا يُسلَّم الوكيلُ سرّاً.

## صيغةُ الأمر
```json
{"action": "dispatch", "workflow": "realign_surah.yml",
 "inputs": {"parent": "timings/hafs/x.jz", "surahs": "6", "skip_ms": "7840",
            "url_template": "https://…/{s:03d}.mp3", "reciter_id": "x",
            "riwaya": "hafs", "reason": "…"}}

{"action": "tool", "tool": "index_qa/run.py", "args": ["--struct-only", "timings-staging/…jz"]}
{"action": "tool", "tool": "ci_fleet/restore_loop.py", "args": ["scan", "--limit", "3"]}
{"action": "state"}                      ← جردٌ كاملٌ من الدلو إلى ops/out/state.json
```

⛔ **وقائمةُ المسموح مغلقة** (‏`ALLOWED_*`): أمرٌ خارجَها يُردّ ويُكتب سببُ ردّه.
⛔ **ولا شيءَ هنا يمسّ العتبات ولا الحُرّاس** — `promote.py` يحكم بحُرّاسه كما هو.
⛔ **والأمرُ المنفَّذُ يُنقل إلى `ops/commands/done/`** فلا يُعاد تنفيذُه عند كلّ دفعة.
"""
from __future__ import annotations

import json
import subprocess
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
CMD_DIR = ROOT / "ops" / "commands"
OUT_DIR = ROOT / "ops" / "out"
DONE_DIR = CMD_DIR / "done"

# ⛔ سيرُ العملِ المسموحُ إطلاقُه — والثقيلُ كلُّه هنا فلا حاجةَ إلى غيره.
ALLOWED_WF = {"align.yml", "realign_surah.yml", "openers.yml", "audio_qa.yml",
              "basmala.yml", "restore.yml", "keepalive.yml", "mirror_reciter.yml",
              "reciter_probe.yml", "probe_ayah.yml", "diagnosis.yml", "timing_ingest.yml"}
# ⛔ والأدواتُ المسموحةُ كلُّها **قارئةٌ أو محكومةٌ بحُرّاسها** — لا صدفةَ فيها.
ALLOWED_TOOLS = {"index_qa/run.py", "index_qa/triage.py", "index_qa/promote.py",
                 "index_qa/bucket_watch.py", "index_qa/drop_surah.py",
                 "index_qa/low_coverage_scan.py", "index_qa/dup_sha_sweep.py",
                 "index_qa/duration_profile.py", "index_qa/reciter_evidence.py",
                 "ci_fleet/restore_loop.py", "ci_fleet/status_page.py",
                 "ci_fleet/repo_parity.py"}
MAX_OUT = 200_000            # حرفاً — جوابٌ أطولُ يُقصّ ويُعلَن قصُّه


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), **kw)
    return p.returncode, (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")


def do_dispatch(c):
    wf = c.get("workflow", "")
    if wf not in ALLOWED_WF:
        return 2, f"⛔ سيرُ عملٍ غيرُ مسموح: {wf!r}\nوالمسموح: {sorted(ALLOWED_WF)}"
    args = ["gh", "workflow", "run", wf]
    for k, v in (c.get("inputs") or {}).items():
        args += ["-f", f"{k}={v}"]
    return run(args)


def do_tool(c):
    tool = c.get("tool", "")
    if tool not in ALLOWED_TOOLS:
        return 2, f"⛔ أداةٌ غيرُ مسموحة: {tool!r}\nوالمسموح: {sorted(ALLOWED_TOOLS)}"
    args = [x if isinstance(x, str) else str(x) for x in (c.get("args") or [])]
    return run([sys.executable, str(ROOT / "tools" / tool), *args])


def do_state(c):
    """جردٌ كاملٌ من الدلو — به يرى الوكيلُ ما لا يصله اعتمادُه."""
    sys.path.insert(0, str(ROOT / "tools" / "index_qa"))
    from run import s3, fetch_index                                   # noqa: E402
    cl, b = s3()
    pub, per = {}, {}
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings/"):
        for o in pg.get("Contents", []):
            k = o["Key"]
            if k.endswith(".jz") and k.count("/") == 2:
                riw = k.split("/")[1]
                pub[(riw, k.split("/")[2][:-3])] = o["Size"]
                per[riw] = per.get(riw, 0) + 1
    cat = json.loads(cl.get_object(Bucket=b, Key="catalog/reciters.json")["Body"].read())
    total = sum(1 for r in cat["riwayat"] for rc in r.get("reciters", [])
                if rc.get("mode") != "ayah")
    gaps = {}
    for (riw, rid) in sorted(pub):
        try:
            idx, _ = fetch_index(f"timings/{riw}/{rid}.jz")
        except Exception:                                             # noqa: BLE001
            continue
        srs = {int(e["ayahId"].split(":")[0]) for e in idx["entries"]}
        miss = [s for s in range(1, 115) if s not in srs]
        if miss or len(idx["entries"]) < 6236:
            tr = idx.get("transform") or {}
            gaps[f"{riw}/{rid}"] = {"entries": len(idx["entries"]),
                                    "missingSurahs": miss,
                                    "reasonCode": tr.get("reasonCode")}
    st = {"published": len(pub), "target": total, "byRiwaya": per,
          "indexesWithGaps": gaps}
    (OUT_DIR / "state.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0, (f"المنشور {len(pub)}/{total} · {per}\n"
               f"فهارسُ فيها نقص: {len(gaps)} — التفصيلُ في ops/out/state.json")


HANDLERS = {"dispatch": do_dispatch, "tool": do_tool, "state": do_state}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    cmds = sorted(p for p in CMD_DIR.glob("*.json"))
    if not cmds:
        print("لا أمرَ جديد."); return
    for f in cmds:
        name = f.stem
        print(f"\n══ أمر: {name}")
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            h = HANDLERS.get(c.get("action"))
            if not h:
                rc, out = 2, (f"⛔ فعلٌ غيرُ معروف: {c.get('action')!r} — "
                              f"والمعروف: {sorted(HANDLERS)}")
            else:
                rc, out = h(c)
        except Exception:                                             # noqa: BLE001
            rc, out = 3, "⛔ تعذّر تنفيذُ الأمر:\n" + traceback.format_exc()
        if len(out) > MAX_OUT:
            out = out[:MAX_OUT] + f"\n… [قُصّ الجواب عند {MAX_OUT} حرفاً]"
        print(out[:4000])
        (OUT_DIR / f"{name}.txt").write_text(
            f"# rc={rc}\n{out}", encoding="utf-8")
        # ⛔ يُنقل المنفَّذُ فلا يُعاد تنفيذُه عند كلّ دفعةٍ تالية
        f.replace(DONE_DIR / f.name)
    print("\n⇒ تمّت الأوامر.")


if __name__ == "__main__":
    main()
