#!/usr/bin/env python3
"""يبحث عن **تسجيلٍ بديلٍ للقارئ نفسِه والرواية نفسِها** لسورةٍ مبتورةٍ عند مصدره.

قراءةٌ محضة: لا يكتب في الدلو ولا في الكتالوج ولا في `source_overrides.json`.
يطبع لكلّ مصحفٍ بديلٍ في mp3quran (‏القارئ ذاته، غير الخادم المسجَّل) نسبةَ حجم
السورة إلى المتوقَّع — **بوسيط أربعة مراجع** كما يقيس المسحُ (`source_ratio`).
والحكمُ «سليم» بالعتبة نفسها `SOUND`؛ ولا يُقترح إلا بديلٌ سليم.

    python tools/ci_fleet/alt_source.py hafs/mukhtar_haj:20,41 hafs/ra3ad:72
    python tools/ci_fleet/alt_source.py --candidates tools/ci_fleet/alt_candidates.json

والصيغةُ الثانية تقيس قوالبَ من مضيفاتٍ أخرى (‏quranicaudio · archive.org · …) جُمعت
بحثاً بشرط «القارئ نفسه والرواية نفسها بدليلٍ مكتوب». القياسُ وحده لا يُثبت الهويّة:
مصدرٌ سليمُ النسبة يُسجَّل في `source_overrides.json` **مع دليل هويّته**، ثم يمرّ
بالمحاذاة والملوح الأربعة وحارس البتر كسائر المصادر.

⛔ القارئُ يُطابَق بمعرّفه في mp3quran (‏صاحبُ الخادم المسجَّل)، لا بتشابه الاسم:
   صوتُ قارئٍ آخر على سورةٍ لا يُنشر أبداً ولو اكتمل العدّ.
⛔ والروايةُ تُطابَق باسم المصحف (‏حفص/ورش/قالون…)، فمصحفُ روايةٍ أخرى لا يُعرض.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import restore_loop as rl                                    # noqa: E402

API = "https://mp3quran.net/api/v3/reciters?language=ar"
# كلمةُ الرواية كما تُكتب في اسم مصحف mp3quran.
RIWAYA_WORD = {"hafs": "حفص", "warsh": "ورش", "qalun": "قالون",
               "douri": "الدوري", "sousi": "السوسي", "shuba": "شعبة",
               "bazzi": "البزي", "qunbul": "قنبل"}


def reciters() -> list:
    req = urllib.request.Request(API, headers={"User-Agent": "rafiq-align-ci"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["reciters"]


def owner_of(allr: list, base: str):
    """القارئُ الذي يملك الخادمَ المسجَّل — بمطابقة الخادم حرفاً."""
    b = base.rstrip("/") + "/"
    for r in allr:
        for m in r["moshaf"]:
            if m["server"].rstrip("/") + "/" == b:
                return r, m
    return None, None


def measure_candidates(path: str, refs) -> int:
    """يقيس كلَّ قالبٍ مرشّح (أو جدولَ ملفّاتٍ بأسماء) على الفهرس المنشور للقارئ."""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    for c in rows:
        riw, rid = c["riwaya"], c["reciter"]
        try:
            idx, _ = rl.fetch_index(f"timings/{riw}/{rid}.jz")
        except Exception as e:                                # noqa: BLE001
            print(f"⛔ {riw}/{rid}: الفهرسُ المنشور متعذّر — {e}")
            continue
        tpl, files = c.get("template") or "", c.get("files") or {}
        print(f"== {riw}/{rid} · {c.get('style', '؟')} · {tpl or 'ملفّاتٌ بأسماء'}")
        print(f"   الدليل: {c.get('evidence', '—')}")
        for s in c.get("surahs") or []:
            if tpl:
                # القالبُ يُحوَّل إلى أساسٍ + جدولِ أسماءٍ حتى تعمل `source_ratio` كما هي.
                names = {n: tpl.split("/")[-1].format(s=n) for n in range(1, 115)}
                base = tpl.rsplit("/", 1)[0] + "/"
            else:
                if str(s) not in files:
                    print(f"   · س{s}: لا رابطَ لها في المرشّح")
                    continue
                base, names = "", {int(k): v for k, v in files.items()}
            size = None
            if not tpl:
                # روابطُ كاملةٌ بأسماء: `source_ratio` تبني «/‏<اسمٍ مُرمَّز>»، فيُفكّ هنا.
                from urllib.parse import unquote                  # noqa: PLC0415
                size = lambda u: rl.head_len(unquote(u.lstrip("/")))  # noqa: E731
            try:
                ratio = rl.source_ratio(idx, base, s, refs, names, size=size)
            except KeyError:
                ratio = None
                print(f"   ⚠️ س{s}: سورُ السبر ليست كلُّها في جدول الروابط — لا قياس")
            except Exception as e:                            # noqa: BLE001
                ratio = None
                print(f"   ⚠️ س{s}: {e}")
            tag = ("سليم" if ratio is not None and ratio >= rl.SOUND
                   else "مبتور/مجهول")
            print(f"   ▶ س{s} · نسبة {ratio} ({tag})")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--candidates"] and len(args) == 2:
        refs = [rl.surah_ends(rl.fetch_index(k)[0]) for k in rl.REFS]
        return measure_candidates(args[1], refs)
    if not args:
        print(__doc__)
        return 0
    bases = rl.catalog_bases()
    refs = []
    for k in rl.REFS:
        try:
            refs.append(rl.surah_ends(rl.fetch_index(k)[0]))
        except Exception as e:                                # noqa: BLE001
            print(f"⚠️ مرجعٌ متعذّر {k}: {e}")
    if len(refs) < 2:
        print("⛔ أقلُّ من مرجعين — والحكمُ بمرجعٍ واحدٍ يُضلّ.")
        return 1
    allr = reciters()
    rc = 0
    for a in args:
        key, _, ss = a.partition(":")
        riw, _, rid = key.partition("/")
        surahs = [int(x) for x in ss.split(",") if x.strip()]
        base = rl.source_base(bases, riw, rid, surahs[0] if surahs else 1)
        if not base:
            print(f"⛔ {key}: لا مصدرَ في الكتالوج — ولا يُخمَّن")
            rc = 1
            continue
        who, cur = owner_of(allr, base)
        if not who:
            print(f"⛔ {key}: الخادمُ المسجَّل {base} ليس في mp3quran — لا مطابقةَ بالمعرّف")
            rc = 1
            continue
        idx, _ = rl.fetch_index(f"timings/{riw}/{rid}.jz")
        word = RIWAYA_WORD.get(riw, "")
        print(f"== {key} · {who['name']} (‏id {who['id']}) · المسجَّل: {base}")
        alts = [m for m in who["moshaf"]
                if m["server"].rstrip("/") != base.rstrip("/")]
        if not alts:
            print("   لا مصحفَ آخرَ لهذا القارئ في mp3quran.")
        for m in alts:
            if word and word not in m["name"]:
                print(f"   ⏭️ {m['name']}: روايةٌ أخرى — لا يُعرض")
                continue
            have = {int(x) for x in str(m.get("surah_list", "")).split(",") if x}
            alt = m["server"].rstrip("/") + "/"
            for s in surahs:
                if s not in have:
                    print(f"   · {m['name']}: س{s} ليست فيه")
                    continue
                ratio = rl.source_ratio(idx, alt, s, refs)
                tag = ("سليم" if ratio is not None and ratio >= rl.SOUND
                       else "مبتور/مجهول")
                print(f"   ▶ س{s} · {m['name']} · {alt} · نسبة {ratio} ({tag})")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
