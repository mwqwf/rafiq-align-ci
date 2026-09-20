#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يطبع محتوى **مخرَج تشغيلةٍ** (artifact) نصّاً — قراءةٌ محضةٌ لا تكتب بايتاً.

    python tools/ci_fleet/show_artifact.py <run_id> [--name-contains ctc] [--max-bytes 20000]

⛔ **العطبُ الذي وُلد منه (مقيسٌ 2026-09-20):** سبرُ CTC بلا رفع (`probe_surahs`)
يضع حكمَه كلَّه في مخرَجٍ صغير (‏`s102.json` · 1861 بايت)، **وسجلُّ الشوط يُقصّ
من ذيله** فلا تصل الأسطرُ الحاسمة. ⇒ فالمناوبةُ ترى `conclusion=success` ولا ترى
**ماذا وجد المحرّك** — و«أُطلق» ليست «تمّ»، والسجلُّ ليس حكماً.

⚖️ ولا يُضعف حارساً ولا يفتح باباً للكتابة: `gh api` قراءةً، وفكُّ الضغط في
مجلّدٍ مؤقّت، وطباعةٌ بسقفِ بايتات. ولا يمسّ الدلوَ ولا عتبةً ولا قائمةَ حجب.
"""
from __future__ import annotations
import argparse, io, json, subprocess, sys, zipfile

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

REPO = "mwqwf/rafiq-align-ci"


def gh_json(path: str):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"⛔ gh api {path}: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--name-contains", default="")
    ap.add_argument("--max-bytes", type=int, default=20000)
    a = ap.parse_args()

    arts = gh_json(f"repos/{REPO}/actions/runs/{a.run_id}/artifacts").get("artifacts", [])
    arts = [x for x in arts if a.name_contains in x["name"]]
    if not arts:
        print("⛔ لا مخرَجَ مطابق."); return 1
    for art in arts:
        print(f"📦 {art['name']} · {art['size_in_bytes']} بايت")
        raw = subprocess.run(
            ["gh", "api", f"repos/{REPO}/actions/artifacts/{art['id']}/zip"],
            capture_output=True)
        if raw.returncode:
            print(f"   ⛔ تنزيلٌ متعذّر: {raw.stderr.decode('utf-8', 'replace')[:200]}")
            continue
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw.stdout))
        except Exception as e:                                   # noqa: BLE001
            print(f"   ⛔ ليس zip: {e}"); continue
        for nm in zf.namelist():
            body = zf.read(nm)
            print(f"── {nm} ({len(body)} بايت)")
            try:
                print(body[:a.max_bytes].decode("utf-8", "replace"))
            except Exception:                                    # noqa: BLE001
                print("   (ثنائيّ — لا يُطبع)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
