#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسبارُ عنصرٍ منفردٍ في archive.org لسورةٍ غائبةٍ عند قارئ — قارئٌ محض.

    python tools/ci_fleet/ia_item_probe.py qalun/akri_qalun 24=024-mp-3_20230509 \
        [107=<عنصر>] [--find 107 "مروان العكري" "العكري"]

لكلّ (سورة=عنصر):
  • بياناتُ العنصر كاملةً (‏العنوان · الوصف · الموضوع · المنشئ) ليُقرأ دليلُ الرواية نصّاً.
  • قائمةُ ملفّاته كلّها بصيغتها وحجمها ومدّتها ومعدّلها كما يُعلنها archive.org.
  • لكلّ ملفّ MP3: تنزيلٌ في ذاكرةٍ مؤقّتة، وعدُّ إطاراته (‏المدّةُ الفعليّة وتوزيعُ المعدّل
    ⇒ CBR أم VBR)، وترويسةُ Xing/Info/VBRI، ومطابقةُ md5 الناشر.
  • النسبةُ إلى المدّة المتوقَّعة بوسيط المراجع (‏`find_sources.expected_ms` على `restore_loop.REFS`)
    مع كلّ مرجعٍ منفرداً.
و`--find <سورة> <اسم>…`: بحثٌ في archive.org عن عناصرَ تحمل الاسمَ ورقمَ السورة أو اسمَها،
ثم يُسبر كلُّ ما وُجد بالطريقة نفسها.

⛔ لا يكتب في الدلو ولا في `source_overrides.json` ولا يحكم بالهويّة: يطبع أرقاماً ونصوصاً.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "index_qa"))
import restore_loop as rl                                   # noqa: E402
from find_sources import SURAH_AR, BAD_TAGS, RIWAYA_WORDS_ALL, expected_ms, ia_len, ia_query  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (rafiq-align-ci probe)"}
MAX_BYTES = 120 * 1024 * 1024


def get(url: str, timeout=300) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def frames(d: bytes) -> dict:
    """عدُّ الإطارات بتتبّع طول كلّ إطار — المدّةُ وتوزيعُ المعدّل وترويسةُ VBR."""
    import mp3dur                                           # noqa: PLC0415
    i = 0
    if d[:3] == b"ID3":
        i = 10 + ((d[6] & 0x7f) << 21 | (d[7] & 0x7f) << 14 | (d[8] & 0x7f) << 7 | (d[9] & 0x7f))
    first = i
    t, n, brs, sr0 = 0.0, 0, {}, None
    while i < len(d) - 4:
        if d[i] == 0xFF and (d[i + 1] & 0xE0) == 0xE0:
            ver = (d[i + 1] >> 3) & 3; layer = (d[i + 1] >> 1) & 3
            bri = (d[i + 2] >> 4) & 0xF; sri = (d[i + 2] >> 2) & 3; pad = (d[i + 2] >> 1) & 1
            if not (ver == 1 or layer == 0 or bri in (0, 15) or sri == 3):
                lay = 4 - layer
                br = (mp3dur.BR if ver == 3 else mp3dur.BR2)[lay if ver == 3 else (1 if lay == 1 else 2)][bri] * 1000
                sr = mp3dur.SR[ver][sri]
                if lay == 1:
                    flen, spf = (12 * br // sr + pad) * 4, 384
                else:
                    spf = 1152 if (lay == 2 or ver == 3) else 576
                    flen = (spf // 8 * br) // sr + pad
                if flen > 0:
                    if n == 0:
                        first = i
                        sr0 = sr
                    brs[br // 1000] = brs.get(br // 1000, 0) + 1
                    t += spf / sr; n += 1; i += flen
                    continue
        i += 1
    head = d[first:first + 200]
    tag = next((x for x in ("Xing", "Info", "VBRI") if x.encode() in head), None)
    kind = "VBR" if (len(brs) > 1 or tag in ("Xing", "VBRI")) else "CBR"
    return {"sec": round(t, 2), "frames": n, "sr": sr0, "bitrates": dict(sorted(brs.items())),
            "vbr_header": tag, "kind": kind}


def probe(key: str, s: int, ident: str, idx, refs) -> None:
    d = rl.surah_ends(idx)
    allx, exp = expected_ms(idx, refs, s)
    print(f"\n== س{s} ‹{SURAH_AR[s-1].replace('_', ' ')}› ⇄ {ident}")
    print(f"   المتوقَّع (وسيط {len(allx)} مراجع) ≈ {exp and round(exp / 1000, 1)}ث · "
          f"كلُّ مرجع: {[round(x / 1000, 1) for x in allx]} · في الفهرس المنشور: "
          f"{round(d[s] / 1000, 1) if d.get(s) else 'غائبة'}ث")
    try:
        meta = json.loads(get(f"https://archive.org/metadata/{ident}", 60))
    except Exception as e:                                  # noqa: BLE001
        print(f"   ⛔ البيانات: {type(e).__name__}: {e}")
        return
    md = meta.get("metadata", {})
    for k in ("title", "description", "subject", "creator", "date", "uploader", "addeddate",
              "collection", "language"):
        if md.get(k):
            print(f"   {k}: {json.dumps(md.get(k), ensure_ascii=False)[:1200]}")
    blob = " ".join(str(md.get(k, "")) for k in ("title", "description", "subject", "creator"))
    bad = [x for x in BAD_TAGS if x in blob]
    riw = [w for w in RIWAYA_WORDS_ALL if w in blob.lower()]
    print(f"   كلماتُ الرواية في النصّ: {riw} · وسومُ المعالجة: {bad}")
    files = meta.get("files", [])
    print(f"   الملفّات ({len(files)}):")
    for f in files:
        print(f"     - {f.get('name')} · {f.get('format')} · {f.get('size')} ب · "
              f"length={f.get('length')} · bitrate={f.get('bitrate')} · source={f.get('source')}")
    for f in files:
        name = f.get("name", "")
        if not name.lower().endswith(".mp3"):
            continue
        url = f"https://archive.org/download/{ident}/{urllib.parse.quote(name)}"
        ln = ia_len(f.get("length"))
        print(f"   ▶ {name}")
        print(f"     مُعلَن: {ln}ث · نسبة/وسيط {ln and exp and round(ln * 1000 / exp, 3)} · "
              f"نسبة/كلّ مرجع {[round(ln * 1000 / x, 3) for x in allx] if ln else '—'}")
        if int(f.get("size") or 0) > MAX_BYTES:
            print("     ⛔ أكبر من السقف — لا تنزيل")
            continue
        try:
            raw = get(url)
        except Exception as e:                              # noqa: BLE001
            print(f"     ⛔ تنزيل: {type(e).__name__}: {e}")
            continue
        md5 = hashlib.md5(raw).hexdigest()
        fr = frames(raw)
        print(f"     منزَّل {len(raw)} ب · md5 {md5} "
              f"({'يطابق' if md5 == f.get('md5') else '⛔ لا يطابق'} الناشر) · إطارات: "
              f"{json.dumps(fr, ensure_ascii=False)}")
        if exp:
            print(f"     المدّةُ بعدّ الإطارات ÷ المتوقَّع = {round(fr['sec'] * 1000 / exp, 3)} · "
                  f"كلُّ مرجع {[round(fr['sec'] * 1000 / x, 3) for x in allx]}")


def find(s: int, names) -> list:
    sname = SURAH_AR[s - 1].replace("_", " ")
    out = {}
    for n in names:
        for q in (f'title:("{n}") AND title:("{s:03d}")',
                  f'title:("{n}") AND title:("{sname}")',
                  f'"{n}" AND title:("سورة {sname}")',
                  f'"{n}" AND mediatype:(audio) AND title:("{s:03d}")'):
            for d in ia_query(q):
                out.setdefault(d["identifier"], d.get("title") or "")
    print(f"\n## بحث س{s} ‹{sname}› بالأسماء {names}: {len(out)} عنصراً")
    for i, t in out.items():
        print(f"   · {i} · «{t}»")
    return [i for i, t in out.items() if f"{s:03d}" in t or f"سورة {sname}" in t]


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 0
    key = a[0]
    riw, _, rid = key.partition("/")
    pairs, finds, k = [], [], 1
    while k < len(a):
        if a[k] == "--find":
            s = int(a[k + 1]); names = []
            k += 2
            while k < len(a) and not a[k].startswith("--") and "=" not in a[k]:
                names.append(a[k]); k += 1
            finds.append((s, names))
            continue
        s, _, ident = a[k].partition("=")
        pairs.append((int(s), ident)); k += 1
    refs = []
    for r in rl.REFS:
        try:
            refs.append(rl.surah_ends(rl.fetch_index(r)[0]))
        except Exception as e:                              # noqa: BLE001
            print(f"⚠️ مرجعٌ متعذّر {r}: {e}")
    idx, _ = rl.fetch_index(f"timings/{riw}/{rid}.jz")
    print(f"# {key} · مراجع {len(refs)} من {rl.REFS}")
    for s, names in finds:
        for ident in find(s, names):
            if (s, ident) not in pairs:
                pairs.append((s, ident))
    for s, ident in pairs:
        probe(key, s, ident, idx, refs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
