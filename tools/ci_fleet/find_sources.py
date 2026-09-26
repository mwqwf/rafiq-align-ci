#!/usr/bin/env python3
"""يبحث **من الأكشنز** عن مضيفاتٍ أخرى لتسجيل القارئ نفسِه، ثم يقيسها — قراءةٌ محضة.

    python tools/ci_fleet/find_sources.py hafs/mukhtar_haj:20,41 qalun/akri_qalun:24,107
    python tools/ci_fleet/find_sources.py --search hafs/nufais:46,47 "أحمد النفيس" "النفيس"

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


def show_files(ident: str, surahs) -> int:
    """يطبع أسماءَ ملفّات السور المطلوبة في عنصر archive.org وحجمَها — لتسجيل قالبٍ صحيح."""
    table = archive_numbered(ident) or {}
    for s in surahs:
        n = table.get(s)
        url = f"https://archive.org/download/{ident}/{urllib.parse.quote(n)}" if n else None
        print(f"{ident} س{s}: {n} · {url} · {rl.head_len(url) if url else '—'} بايت")
    return 0


# أسماءُ السور (‏بلا «سورة») للبحث في عناوين archive.org — مفهرسةٌ برقم السورة.
SURAH_AR = ("الفاتحة البقرة آل_عمران النساء المائدة الأنعام الأعراف الأنفال التوبة يونس هود "
            "يوسف الرعد إبراهيم الحجر النحل الإسراء الكهف مريم طه الأنبياء الحج المؤمنون النور "
            "الفرقان الشعراء النمل القصص العنكبوت الروم لقمان السجدة الأحزاب سبأ فاطر يس الصافات "
            "ص الزمر غافر فصلت الشورى الزخرف الدخان الجاثية الأحقاف محمد الفتح الحجرات ق الذاريات "
            "الطور النجم القمر الرحمن الواقعة الحديد المجادلة الحشر الممتحنة الصف الجمعة المنافقون "
            "التغابن الطلاق التحريم الملك القلم الحاقة المعارج نوح الجن المزمل المدثر القيامة الإنسان "
            "المرسلات النبأ النازعات عبس التكوير الانفطار المطففين الانشقاق البروج الطارق الأعلى "
            "الغاشية الفجر البلد الشمس الليل الضحى الشرح التين العلق القدر البينة الزلزلة العاديات "
            "القارعة التكاثر العصر الهمزة الفيل قريش الماعون الكوثر الكافرون النصر المسد الإخلاص "
            "الفلق الناس").split()
# وسومُ صوتٍ معالَج: حدرٌ مسرَّعٌ آليّاً أو صوتٌ مُرقَّق — لا يُقبل بديلاً ولو سلمت نسبتُه.
BAD_TAGS = ("حدر مسرع", "مسرع", "مرقق", "مسرّع", "speed", "fast", "x1.", "1.25", "1.5x")
RIWAYA_WORDS_ALL = ("حفص", "ورش", "قالون", "الدوري", "السوسي", "شعبة", "البزي", "قنبل",
                    "warsh", "qalon", "qaloon", "qalun", "hafs")


def expected_ms(idx, refs, s: int):
    """المدّةُ المتوقَّعة للسورة بوسيط المراجع: مدّتُها عند المرجع × معامل سرعة القارئ
    (‏نسبةُ مجموع سوره المشتركة إلى مجموعها عند المرجع، بلا السورة نفسها)."""
    d = rl.surah_ends(idx)
    outs = []
    for rd in refs:
        if not rd.get(s):
            continue
        common = [x for x in d if x in rd and d[x] > 0 and rd[x] > 0 and x != s]
        if common:
            outs.append(rd[s] * sum(d[x] for x in common) / sum(rd[x] for x in common))
    return sorted(outs), (sorted(outs)[len(outs) // 2] if outs else None)


def ia_query(q: str, rows: int = 200) -> list:
    url = IA_SEARCH + "?" + urllib.parse.urlencode(
        {"q": q, "fl[]": ["identifier", "title"], "rows": rows, "output": "json"}, doseq=True)
    try:
        return get_json(url)["response"]["docs"]
    except Exception as e:                                    # noqa: BLE001
        print(f"      ⚠️ archive.org «{q}»: {e}")
        return []


def ia_len(v) -> float | None:
    """طولُ الملفّ في بيانات archive.org: ثوانٍ عشريّة أو «س:د:ث»."""
    if v is None:
        return None
    v = str(v)
    try:
        if ":" in v:
            sec = 0.0
            for part in v.split(":"):
                sec = sec * 60 + float(part)
            return sec
        return float(v)
    except ValueError:
        return None


def search_mode(args) -> int:
    """`--search <رواية/قارئ:سور> <اسم> [<اسم>…]` — بحثٌ لكلّ سورةٍ بعينها بأسماءٍ صريحة،
    وقياسٌ **بالمدّة** (‏حقل length في archive.org) لا بالحجم، بوسيط المراجع؛ فيصلح
    للعناصر ذات السورة الواحدة التي لا سُوَر سبرٍ فيها. ⛔ مطابقةُ الاسم دليلٌ للمراجعة لا حكم."""
    key, _, ss = args[0].partition(":")
    riw, _, rid = key.partition("/")
    surahs = [int(x) for x in ss.split(",") if x.strip()]
    names = args[1:]
    refs = []
    for k in rl.REFS:
        try:
            refs.append(rl.surah_ends(rl.fetch_index(k)[0]))
        except Exception as e:                                # noqa: BLE001
            print(f"⚠️ مرجعٌ متعذّر {k}: {e}")
    idx, _ = rl.fetch_index(f"timings/{riw}/{rid}.jz")
    word = RIWAYA_WORD.get(riw, "")
    print(f"\n== {key} · س{surahs} · الأسماء: {names} · مراجع {len(refs)}")
    seen_meta = {}
    for s in surahs:
        allx, exp = expected_ms(idx, refs, s)
        print(f"   ‹س{s} {SURAH_AR[s-1].replace('_', ' ')}› المتوقَّع ≈ "
              f"{exp and round(exp / 1000)} ث (المراجع: {[round(x / 1000) for x in allx]})")
        docs = {}
        for n in names:
            for q in (f'title:("{n}") AND title:("{s:03d}")',
                      f'title:("{n}") AND title:("{SURAH_AR[s-1].replace("_", " ")}")',
                      f'"{n}" AND mediatype:(audio) AND title:("{s:03d}")',
                      f'title:("{n}") AND mediatype:(audio)'):
                for d in ia_query(q):
                    docs.setdefault(d["identifier"], d.get("title") or "")
        for ident, title in docs.items():
            meta = seen_meta.get(ident)
            if meta is None:
                try:
                    meta = get_json(f"https://archive.org/metadata/{ident}")
                except Exception:                             # noqa: BLE001
                    meta = {}
                seen_meta[ident] = meta
            files = [f for f in meta.get("files", [])
                     if f.get("name", "").lower().endswith(".mp3")]
            md = meta.get("metadata", {})
            blob = " ".join(str(md.get(k, "")) for k in ("title", "description", "subject", "creator"))
            # اختيارُ ملفّ السورة: عنصرُ سورةٍ واحدة، أو ملفٌّ يحمل رقمَها أو اسمَها.
            pick = []
            sname = SURAH_AR[s - 1].replace("_", " ")
            for f in files:
                n = f["name"]
                if (re.search(rf"(?<!\d)0*{s}(?!\d)", n.rsplit("/", 1)[-1])
                        or (len(sname) > 1 and sname in n)):
                    pick.append(f)
            single = len(files) == 1 and (re.search(rf"(?<!\d)0*{s}(?!\d)", title)
                                          or f"سورة {sname}" in title)
            if single:
                pick = files
            if not pick:
                continue
            bad = [t for t in BAD_TAGS if t in (title + " " + blob)]
            other = [w for w in RIWAYA_WORDS_ALL if w in (title + " " + blob).lower()
                     and w not in (word, word.lower()) and not (riw == "hafs" and w == "hafs")]
            for f in pick[:3]:
                ln = ia_len(f.get("length"))
                ratio = (ln * 1000 / exp) if (ln and exp) else None
                ok = ratio is not None and 0.9 <= ratio <= 1.35 and not bad
                print(f"      {'✅' if ok else '·'} {ident} · «{title}» · {f['name']} · "
                      f"{f.get('size')} بايت · مدّة {ln and round(ln)} ث · نسبة "
                      f"{ratio and round(ratio, 2)}"
                      f"{' · ⛔ وسمُ معالجة ' + str(bad) if bad else ''}"
                      f"{' · ⚠️ روايةٌ أخرى مذكورة ' + str(other) if other else ''}"
                      f"{' · ✔ الروايةُ مذكورة' if word and word in blob + title else ''}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--search"] and len(args) >= 3:
        return search_mode(args[1:])
    if args[:1] == ["--files"]:
        return show_files(args[1], [int(x) for x in args[2].split(",")])
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
