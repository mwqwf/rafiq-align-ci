#!/usr/bin/env python3
"""🧭 خطّةُ private-ci — تفحص الحدثَ وحمولتَه وتُخرج مصفوفةَ الأشواط.

⛔ الحمولةُ (client_payload) علنيّةٌ في بيانات الحدث وغيرُ موثوقة: تُقرأ من متغيّر بيئة لا من حقنٍ في الصدفة،
   ولا يُقبل فيها إلا مفتاحان بالضبط: sha (أربعون حرفاً ست عشريّاً) وkind (من kinds.json وحده).
⛔ ولا تُطبع قيمةٌ واردةٌ عند الرفض — رسالةٌ ثابتةٌ فقط، فلا يصير السجلُّ العلنيّ مرآةً لما أرسله أيٌّ كان.
✅ workflow_dispatch لا يجري إلا تجربةً (dry_run=true) على المستودع العامّ نفسِه؛ ولا طريقَ منه إلى الخاص.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHA_RE = re.compile(r"[0-9a-f]{40}")


def load_kinds(path=None):
    with open(path or os.path.join(HERE, "kinds.json"), encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def decide(event, payload_json, dry_run, plant, head_sha, kinds):
    """تُعيد (dict للمخرجات) أو ترفع ValueError برسالةٍ ثابتة لا تحمل قيمةً واردة."""
    if event == "workflow_dispatch":
        if str(dry_run).lower() != "true":
            raise ValueError("⛔ التشغيلُ اليدويّ تجربةٌ فقط (dry_run=true) — ولا يُستنسخ منه المستودعُ الخاص")
        if not SHA_RE.fullmatch(head_sha or ""):
            raise ValueError("⛔ رأسُ المستودع العام غيرُ صالح")
        kind, sha = "dry-run", head_sha
    elif event == "repository_dispatch":
        try:
            payload = json.loads(payload_json or "null")
        except ValueError:
            raise ValueError("⛔ حمولةٌ غيرُ مقروءة")
        if not isinstance(payload, dict) or set(payload) != {"sha", "kind"}:
            raise ValueError("⛔ الحمولةُ يجب أن تحمل sha وkind وحدهما")
        sha, kind = payload["sha"], payload["kind"]
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise ValueError("⛔ sha غيرُ صالح")
        if not isinstance(kind, str) or kind not in kinds or kind == "dry-run":
            raise ValueError("⛔ نوعُ مهمّةٍ غيرُ مسموح")
        plant = "false"
    else:
        raise ValueError("⛔ حدثٌ غيرُ مسموح")
    spec = kinds[kind]
    legs = []
    for leg in spec["legs"]:
        item = {"id": leg["id"], "timeout": int(leg.get("timeout", 60)), "lint": bool(leg.get("lint", False)),
                "has_emu": "emu" in leg, "emu": leg.get("emu", {"api": 0, "target": "", "arch": "", "profile": "", "ram": ""})}
        legs.append(item)
    return {
        "kind": kind,
        "sha": sha,
        "source": spec["source"],
        "context": spec["context"],
        "multi": "true" if len(legs) > 1 else "false",
        "plant": "true" if str(plant).lower() == "true" else "false",
        "legs": json.dumps(legs, ensure_ascii=False, separators=(",", ":")),
    }


def main():
    e = os.environ
    try:
        out = decide(e.get("PCI_EVENT", ""), e.get("PCI_PAYLOAD", ""), e.get("PCI_DRY_RUN", ""),
                     e.get("PCI_PLANT", "false"), e.get("PCI_HEAD_SHA", ""), load_kinds())
    except ValueError as err:
        print(str(err))
        return 1
    with open(e["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        for k, v in out.items():
            f.write(f"{k}={v}\n")
    # ✅ ما يُطبع: النوعُ وعددُ الأشواط فقط (‏والـSHA علنيٌّ أصلاً في الحمولة).
    print(f"الخطّة: {out['kind']} · {len(json.loads(out['legs']))} شوط · المصدر {out['source']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
