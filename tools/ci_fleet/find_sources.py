#!/usr/bin/env python3
"""يبحث **من الأكشنز** عن مضيفاتٍ أخرى لتسجيل القارئ نفسِه، ثم يقيسها — قراءةٌ محضة.

    python tools/ci_fleet/find_sources.py hafs/mukhtar_haj:20,41 qalun/akri_qalun:24,107

لكلّ قارئ:
  1) اسمُه العربيّ من mp3quran بمطابقة **خادمه المسجَّل حرفاً** (‏لا بالاسم).
  2) مصاحفُه الأخرى في mp3quran من الرواية نفسها.
  3) quranicaudio: قارئٌ **اسمُه العربيُّ مطابقٌ بعد التطبيع**.
  4) archive.org: عناصرُ صوتيّةٌ في عنوانها الاسمُ كاملاً — تُسرد للمراجعة، وتُقاس
     إن كان فيها ملفّاتُ سورٍ مرقّمة.
ثم نسبةُ مدّة السور المطلوبة في كلّ مرشّحٍ بوسيط أربعة مراجع (`restore_loop.source_ratio`).

⛔ مطابقةُ الاسم **دليلٌ للمراجعة لا حكمٌ بالهويّة**: لا يُكتب شيءٌ في
   `source_overrides.json` من هنا. الكتابةُ تكون بيدٍ تقرأ الدليل وتتحقّق من الرواية.
⛔ لا يُنزَّل صوتٌ هنا: الحجمُ بطلب HEAD وحده.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import restore_loop as rl                                    # noqa: E402
from alt_source import RIWAYA_WORD, owner_of, reciters       # noqa: E402

UA = {"User-Agent": "rafiq-align-ci"}
QA_API = "https://quranicaudio.com/api/qaris"
QA_DL = "https://download.quranicaudio.com/quran/"
IA_SEARCH = "https://archive.org/advancedsearch.php"


def get_json(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def norm(name: str) -> str:
    """تطبيعُ الاسم العربيّ للمطابقة: بلا تشكيلٍ ولا «ال» ولا همزاتٍ ولا مسافاتٍ زائدة."""
    n = re.sub(r"[ً-ْـ]", "", name or "")
    n = re.sub(r"[أإآ]", "ا", n).replace("ة", "ه").replace("ى", "ي")
    n = re.sub(r"\bال", "", n)
    n = re.sub(r"[^ء-ي ]", " ", n)
    return " ".join(n.split())


def measure(idx, refs, label: str, base: str, surahs, names=None):
    for s in surahs:
        ratio = rl.source_ratio(idx, base, s, refs, names)
        tag = "سليم" if ratio is not None and ratio >= rl.SOUND else "مبتور/مجهول"
        print(f"      ▶ س{s} · {label} · نسبة {ratio if ratio is None else round(ratio, 2)} ({tag})")


def quranicaudio(qaris, name: str):
    want = norm(name)
    out = []
    for q in qaris:
        if norm(q.get("arabic_name") or "") == want and q.get("relative_path"):
            out.append(q)
    return out


def archive_items(name: str) -> list:
    q = f'title:("{name}") AND mediatype:(audio)'
    url = IA_SEARCH + "?" + urllib.parse.urlencode(
        {"q": q, "fl[]": ["identifier", "title"], "rows": 25, "output": "json"},
        doseq=True)
    try:
        return get_json(url)["response"]["docs"]
    except Exception as e:                                    # noqa: BLE001
        print(f"      ⚠️ archive.org: {e}")
        return []


def archive_numbered(ident: str):
    """جدولُ `{سورة: رابط}` إن كانت ملفّاتُ العنصر مرقّمةً بالسورة بوضوح (‏001…114)."""
    try:
        meta = get_json(f"https://archive.org/metadata/{ident}")
    except Exception:                                         # noqa: BLE001
        return None
    table = {}
    for f in meta.get("files", []):
        n = f.get("name", "")
        if not n.lower().endswith(".mp3"):
            continue
        m = re.fullmatch(r"(?:.*/)?0*(\d{1,3})\.mp3", n, re.I)
        if m and 1 <= int(m.group(1)) <= 114:
            table[int(m.group(1))] = n
    return table if len(table) >= 100 else None


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 0
    bases = rl.catalog_bases()
    refs = [rl.surah_ends(rl.fetch_index(k)[0]) for k in rl.REFS]
    allr = reciters()
    try:
        qaris = get_json(QA_API)
        qaris = qaris.get("qaris", qaris) if isinstance(qaris, dict) else qaris
    except Exception as e:                                    # noqa: BLE001
        print(f"⚠️ quranicaudio متعذّر: {e}")
        qaris = []
    for a in args:
        key, _, ss = a.partition(":")
        riw, _, rid = key.partition("/")
        surahs = [int(x) for x in ss.split(",") if x.strip()]
        base = rl.source_base(bases, riw, rid, surahs[0] if surahs else 1)
        who, _cur = owner_of(allr, base) if base else (None, None)
        print(f"\n== {key} · س{surahs}")
        if not who:
            print(f"   ⛔ الخادمُ المسجَّل ({base}) ليس في mp3quran — لا اسمَ موثوقٌ للبحث")
            continue
        name = who["name"]
        print(f"   الاسم: {name} (‏mp3quran id {who['id']}) · المسجَّل: {base}")
        try:
            idx, _ = rl.fetch_index(f"timings/{riw}/{rid}.jz")
        except Exception as e:                                # noqa: BLE001
            print(f"   ⛔ الفهرسُ المنشور متعذّر: {e}")
            continue
        word = RIWAYA_WORD.get(riw, "")
        for m in who["moshaf"]:
            srv = m["server"].rstrip("/") + "/"
            if srv == base.rstrip("/") + "/":
                continue
            if word and word not in m["name"]:
                continue
            print(f"   [mp3quran] {m['name']} · {srv}")
            measure(idx, refs, "mp3quran", srv, surahs)
        for q in quranicaudio(qaris, name):
            srv = QA_DL + q["relative_path"].strip("/") + "/"
            print(f"   [quranicaudio] {q.get('arabic_name')} / {q.get('name')} · "
                  f"{srv} · ⚠️ تُتحقّق الروايةُ يدوياً")
            measure(idx, refs, "quranicaudio", srv, surahs)
        for d in archive_items(name):
            ident, title = d.get("identifier"), d.get("title")
            table = archive_numbered(ident)
            print(f"   [archive.org] {ident} · «{title}» · "
                  f"{'مرقّمٌ ' + str(len(table)) if table else 'غيرُ مرقّم — للمراجعة'}")
            if table:
                srv = f"https://archive.org/download/{ident}/"
                measure(idx, refs, "archive.org", srv, surahs, table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
