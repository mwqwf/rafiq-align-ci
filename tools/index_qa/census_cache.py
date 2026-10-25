# -*- coding: utf-8 -*-
"""إعادةُ استعمال أحكام الإحصاء الشامل على مستوى السورة — حين تتطابق المدخلاتُ بايتاً بايتاً.

## لماذا
القارئ الواحد يُرقّى عشرات المرّات، وكلُّ جولةٍ تغيّر نحو خمس سورٍ فقط، ومع ذلك يُعاد سماعُ
كلِّ سورةٍ في `promote.census_surahs(idx)`. فالسورةُ التي لم يتغيّر فيها شيءٌ تُسمع بالنموذج
نفسِه على الصوت نفسِه فتعطي الصفوفَ نفسَها. هذه الوحدةُ تحفظ صفوفَ السورة السليمة
الحاسمة في `state-census-cache/` وتعيدها حين يتطابق **كلُّ** ما يؤثّر في الحكم.

## ما لا تفعله (حدودٌ لا تُكسر — أمر المالك)
- لا تمسّ `promote.census_gate` ولا الشهودَ ولا أيَّ عتبة (5% · «غير حاسم» > النصف). التقريرُ
  المركّب يمرّ عليها كما هي أو يُردّ كما هو.
- لا تُعيد إلا سورةً **كاملةً سليمةً حاسمة**: كلُّ صفوفها «بريء» (‏لا «طفيف»)، لا «تعذّر» ولا
  «غير حاسم» ولا «جسيم»، ولا نافذةَ خطأٍ في أيٍّ من نوافذها. وما سوى ذلك يُسمع من جديد دائماً.
- لا تكتب إلا من CI (المصدرُ `ci` ومعرّفُ تشغيلٍ رقميٌّ وبيئةُ Actions)، وفي بادئةٍ معزولة
  `state-census-cache/` لا يقرؤها أيُّ قارئٍ آخر (لا `state/` ولا `state-census/`).
- مفتاحُ إطفاءٍ: المتغيّر `QA_CENSUS_NO_REUSE=1` (ومدخلُ `reuse_census` في سير العمل) يعيد
  السلوكَ القديم كلَّه: لا قراءةَ كاش ولا كتابةَ كاش.

## مفتاح الكاش (والشكُّ يُدخَل ولا يُهمَل — الخطأ المقبول إعادةٌ زائدة)
الرواية · القارئ · رقم السورة · ترويسةُ السورة (`engineVersion` و`engineBySurah` و`sourceBySurah`
و`sourceTimingBySurah`) · **بصمةُ ملفّ الصوت** `audioSha256[s-1]` (غيابُها ⇒ لا كاش) · روابطُ
الملفّات `fileRef` · نهايةُ آخر مدخلٍ في كلّ ملفّ (تدخل في حشو نهاية الملفّ وقد تأتي من سورةٍ
أخرى تشاركه) · **بصمةُ كلّ حقلٍ في كلّ مدخلٍ في السورة** · بصمةُ النصّ المرجعي للرواية · بصمةُ
النموذج (ملفُّه نفسُه) · بصمةُ نصّ كلّ وحدةٍ بايثونيةٍ تشارك في الحكم (إغلاقٌ سكونيٌّ على
الاستيرادات) · ثوابتُ النوافذ · إصداراتُ الأدوات (ffmpeg وpywhispercpp وnumpy وsoundfile) ·
وما يؤثّر من البيئة (`QA_NO_RANGE`).

⛔ ولا يدخل في المفتاح: بصمةُ الفهرس كلِّه ولا `transform` — فهما يتغيّران في كلّ مرشّح وهما
سببُ الإهدار؛ وما يقرؤه الحكمُ من الفهرس يدخل كلُّه عبر مداخل السورة وترويستها.
"""
from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

SCHEMA = 1
PREFIX = "state-census-cache/"
OFF_ENV = "QA_CENSUS_NO_REUSE"
# ‏ما يؤثّر في الحكم من متغيّرات البيئة (‏يُقرأ كما هو لا بعد تأويل).
ENV_KEYS = ("QA_NO_RANGE",)
# ‏لا يُعاد إلا «بريء» حاسم (‏شُدّد: «طفيف» حكمُ عطبٍ وإن صغر فيُسمع من جديد)؛ وما سواه يُسمع دائماً.
REUSABLE_KINDS = ("بريء",)
_ROW_KEYS = {"aid", "cluster", "verdict", "kind", "why", "band", "startApprox",
             "noPreAudio", "heard"}
_WINDOW_PREFIXES = ("F", "L", "D")

ROOT = Path(__file__).resolve().parents[2]
SEARCH_DIRS = (ROOT / "tools" / "index_qa", ROOT / "tools" / "alignment",
               ROOT / "tools" / "alignment_v3")
# ‏جذورُ إغلاق الشيفرة: مولِّدُ الصفوف (‏R) والمُشغِّل والكاش وما يستورده المُشغِّل (‏promote)
# ‏والشهودُ الثلاثة التي تقرأ التقريرَ المركّب. وكلُّ ما تستورده هذه (‏ولو داخل دالّة) يدخل.
CODE_ROOTS = ("tools/index_qa/run.py", "tools/index_qa/ci_run.py",
              "tools/index_qa/census_cache.py", "tools/index_qa/promote.py",
              "tools/alignment_v3/spoken_census_witness.py",
              "tools/alignment_v3/tail_census_witness.py",
              "tools/alignment_v3/window_census_witness.py")


def canon(obj) -> bytes:
    """تسلسلٌ قانونيٌّ ثابت: مفاتيحُ مرتّبة وبلا مسافات وUTF-8 — أساسُ كلّ بصمة هنا."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def sha(obj) -> str:
    return hashlib.sha256(canon(obj)).hexdigest()


def disabled(env=None) -> bool:
    """مفتاحُ الإطفاء الكلّي: أيُّ قيمةٍ غير فارغةٍ وغير 0/false/no تعني الإطفاء."""
    v = str((os.environ if env is None else env).get(OFF_ENV, "") or "").strip().lower()
    return v not in ("", "0", "false", "no")


def ci_may_write(source, run_id, env=None) -> bool:
    """الكتابةُ من CI وحده: مصدرُ `ci` ومعرّفُ تشغيلٍ رقميٌّ وبيئةُ Actions الفعليّة."""
    env = os.environ if env is None else env
    return (source == "ci" and str(run_id or "").isdigit()
            and env.get("GITHUB_ACTIONS") == "true")


# ───────────────────────── بصمة الشيفرة ─────────────────────────
def _imports_of(tree, file_dir):
    """أسماءُ الوحدات المستوردة في الشجرة كلِّها (‏ومنها ما داخل الدوالّ) مع مكانها المحتمل."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, 0) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            out.append((base, node.level))
            out += [((base + "." if base else "") + a.name, node.level) for a in node.names]
    return out


def code_closure(roots, search_dirs=SEARCH_DIRS, base=ROOT):
    """{مسارٌ نسبيّ: بصمة} لكلّ ملفٍّ بايثونيٍّ يبلغه الاستيرادُ من الجذور.

    إغلاقٌ سكونيٌّ فوق مجموعةٍ علوية: اسمٌ يطابق ملفاً في أكثر من مجلّدٍ يُدخَل في كلّها
    (‏تحوّطاً)، والاستيرادُ داخل الدوالّ يُلتقط. ما لم يوجد ملفُّه (‏مكتبةٌ خارجية) يُتخطّى.
    ⛔ استيرادٌ ديناميكيٌّ بالنصّ (‏`importlib`/`__import__`) لا يُلتقط؛ ولا يوجد منه في الجذور
       الحالية — وتتولّى الاختباراتُ إثبات ذلك."""
    base = Path(base)
    seen, todo = {}, [Path(r) if Path(r).is_absolute() else base / r for r in roots]
    while todo:
        p = todo.pop().resolve()
        if p in seen or not p.is_file():
            continue
        data = p.read_bytes()
        try:
            rel = p.relative_to(Path(base).resolve()).as_posix()
        except ValueError:
            rel = p.as_posix()
        seen[p] = (rel, hashlib.sha256(data).hexdigest())
        try:
            tree = ast.parse(data)
        except (SyntaxError, ValueError):
            continue
        dirs = [Path(d) for d in search_dirs] + [p.parent]
        for name, level in _imports_of(tree, p.parent):
            parts = name.split(".") if name else []
            where = [p.parent] if level else dirs
            for d in where:
                rel_parts = Path(*parts) if parts else Path()
                for cand in (d / rel_parts.with_suffix(".py") if parts else None,
                             d / rel_parts / "__init__.py"):
                    if cand is not None and cand.is_file():
                        todo.append(cand)
    return dict(sorted(seen.values()))


def code_digest(roots=CODE_ROOTS, search_dirs=SEARCH_DIRS, base=ROOT) -> str:
    return sha(code_closure(roots, search_dirs, base))


# ───────────────────────── حقائق التشغيل ─────────────────────────
def _version(name):
    try:
        from importlib import metadata
        return metadata.version(name)
    except Exception:                                     # noqa: BLE001
        return None


def runtime_facts() -> dict:
    """إصداراتُ الأدوات التي يتوقّف عليها الفكُّ والتفريغ — وغيابُ أداةٍ حقيقةٌ تدخل المفتاح."""
    try:
        ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=30,
                            check=False).stdout.decode("utf-8", "replace").splitlines()[0]
    except Exception:                                     # noqa: BLE001
        ff = None
    try:
        import soundfile
        sfv = getattr(soundfile, "__libsndfile_version__", None)
    except Exception:                                     # noqa: BLE001
        sfv = None
    return {"python": platform.python_version(), "machine": platform.machine(),
            "system": platform.system(), "ffmpeg": ff, "libsndfile": sfv,
            "pywhispercpp": _version("pywhispercpp"), "numpy": _version("numpy"),
            "soundfile": _version("soundfile")}


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ───────────────────────── صلاحية الصفوف ─────────────────────────
def rows_reusable(rows, aids, surah, err_windows=()):
    """سببُ عدم صلاحية صفوف السورة للحفظ/الإعادة، أو None إن صلحت.

    تصلح السورةُ حين: الصفوفُ هي آياتُها بالضبط (‏بلا نقصٍ ولا تكرار)، وكلُّها «بريء» أو «طفيف»،
    ولا صفَّ «تعذّر»، ولا نافذةَ خطأٍ لآيةٍ منها، ولا حقلَ دخيلاً (‏كشهادٍ مستقلٍّ يعدّل الصفَّ)."""
    aids = list(aids)
    if not aids:
        return "سورةٌ بلا آيات"
    if len(rows) != len(aids) or [r.get("aid") for r in rows] != aids:
        return "الصفوفُ لا تطابق آياتِ السورة"
    for r in rows:
        if not isinstance(r, dict) or set(r) - _ROW_KEYS:
            return "حقولٌ دخيلة في صف"
        if r.get("verdict") == "تعذّر" or r.get("kind") not in REUSABLE_KINDS:
            return f"صفٌّ غيرُ سليمٍ حاسم ({r.get('kind')})"
        if r.get("cluster") != surah or not isinstance(r.get("heard"), dict):
            return "صفٌّ بلا تفريغٍ محفوظ أو بعنقودٍ آخر"
    bad = [w for w in err_windows
           if w.split("|", 1)[-1] in set(aids) and w.split("|", 1)[0] in _WINDOW_PREFIXES]
    if bad:
        return f"نافذةُ خطأٍ في السورة ({bad[0]})"
    return None


# ───────────────────────── الكاش ─────────────────────────
class CensusCache:
    """كاشُ أحكام السور. `static` ما لا يتغيّر في التشغيلة: بصمة الشيفرة والنموذج وحقائق التشغيل."""

    def __init__(self, cl, bucket, static, *, write_ok=False, run_id=None):
        self.cl, self.bucket = cl, bucket
        self.static = dict(static)
        self.write_ok, self.run_id = bool(write_ok), str(run_id or "")
        self.keys = {}        # سورة ⇒ (بصمة المفتاح، مادّته)
        self.hits = {}        # سورة ⇒ وصف المصدر
        self.misses = {}      # سورة ⇒ السبب
        self.pending = {}     # سورة ⇒ ما يُكتب في flush
        self.written = []

    # ‏— بناء المفتاح
    @staticmethod
    def object_key(material, digest):
        return (f"{PREFIX}{material['riwaya']}/{material['reciterId']}/"
                f"{int(material['surah']):03d}/{digest}.json")

    def material(self, idx, s, entries, fend, text_sha, consts):
        """(مادّةُ المفتاح، None) أو (None، سببُ تعذّر بنائه)."""
        from index_fields import audio_shas, IndexFieldError
        try:
            shas = audio_shas(idx)
        except IndexFieldError as ex:
            return None, f"audioSha256 معطوب: {ex}"
        if len(shas) != 114 or not shas[s - 1]:
            return None, "لا بصمةَ صوتٍ لهذه السورة في الترويسة"
        if not entries:
            return None, "سورةٌ بلا مداخل"
        refs = sorted({e.get("fileRef") for e in entries}, key=str)
        if any(not r for r in refs):
            return None, "مدخلٌ بلا fileRef"
        if not idx.get("riwaya") or not idx.get("reciterId"):
            return None, "ترويسةٌ بلا رواية أو قارئ"
        hdr = {k: (idx.get(k) or {}).get(str(s)) if isinstance(idx.get(k), dict) else None
               for k in ("engineBySurah", "sourceBySurah", "sourceTimingBySurah")}
        m = {"schema": SCHEMA, "riwaya": idx["riwaya"], "reciterId": idx["reciterId"],
             "surah": int(s), "engineVersion": idx.get("engineVersion"), **hdr,
             "audioSha256": shas[s - 1], "fileRefs": refs,
             "fileEndMs": {r: fend.get(r) for r in refs},
             "nEntries": len(entries), "entriesSha": sha(entries),
             "textSha": text_sha, "consts": consts, **self.static}
        return m, None

    # ‏— القراءة
    def reuse(self, idx, by_surah, fend, text_sha, consts):
        """{سورة: {aid: صف}} للسور المطابقة؛ وكلُّ ما سواها يُسمع. لا يرفع استثناءً أبداً."""
        out = {}
        for s, entries in sorted(by_surah.items()):
            try:
                m, why = self.material(idx, s, entries, fend, text_sha, consts)
                if m is None:
                    self.misses[s] = why
                    continue
                digest = sha(m)
                self.keys[s] = (digest, m)
                obj = self.object_key(m, digest)
                try:
                    body = self.cl.get_object(Bucket=self.bucket, Key=obj)["Body"].read()
                except Exception:                              # noqa: BLE001
                    self.misses[s] = "لا حكمَ محفوظاً بهذا المفتاح"
                    continue
                src = json.loads(body)
                rows, why = self._validate(src, m, digest, entries)
                if rows is None:
                    self.misses[s] = why
                    continue
                self.hits[s] = {"cacheKey": digest, "object": obj,
                                "runId": src.get("runId"), "indexKey": src.get("indexKey"),
                                "indexSha256": src.get("indexSha256")}
                mark = {"cacheKey": digest, "runId": src.get("runId"), "object": obj}
                out[s] = {r["aid"]: {**copy.deepcopy(r), "reusedFrom": mark} for r in rows}
            except Exception as ex:                            # noqa: BLE001
                self.misses[s] = f"تعذّرت القراءة: {type(ex).__name__}: {str(ex)[:80]}"
        return out

    def _validate(self, doc, material, digest, entries):
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            return None, "صيغةٌ غير معروفة"
        if doc.get("cacheKey") != digest or sha(doc.get("material")) != digest or doc["material"] != material:
            return None, "المفتاحُ المحفوظ لا يطابق مادّته"
        if doc.get("source") != "ci" or not str(doc.get("runId") or "").isdigit():
            return None, "الحكمُ المحفوظ ليس من CI"
        aids = [e["ayahId"] for e in entries]
        why = rows_reusable(doc.get("rows") or [], aids, material["surah"])
        if why:
            return None, "الحكمُ المحفوظ لا يصلح: " + why
        return doc["rows"], None

    # ‏— الكتابة
    def offer(self, s, aids, rows, err_windows):
        """يُعرَض حكمٌ جديد لسورةٍ سُمعت؛ يُحفظ في `pending` إن صلح (‏ويُكتب في flush)."""
        if s not in self.keys:
            return
        why = rows_reusable(rows, aids, s, err_windows)
        if why:
            prev = self.misses.get(s)
            self.misses[s] = (prev + " · " if prev else "") + "لن يُحفظ: " + why
            return
        self.pending[s] = [copy.deepcopy(r) for r in rows]

    def flush(self, index_key=None, index_sha=None):
        """يكتب الأحكام الصالحة — من CI وحده. لا يرفع استثناءً (‏الكاشُ لا يُسقط إحصاءً)."""
        if not self.write_ok:
            return []
        for s, rows in sorted(self.pending.items()):
            digest, m = self.keys[s]
            doc = {"schema": SCHEMA, "cacheKey": digest, "material": m, "source": "ci",
                   "runId": self.run_id, "indexKey": index_key, "indexSha256": index_sha,
                   "writtenAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "rows": rows}
            try:
                self.cl.put_object(Bucket=self.bucket, Key=self.object_key(m, digest),
                                   Body=json.dumps(doc, ensure_ascii=False).encode("utf-8"),
                                   ContentType="application/json; charset=utf-8")
                self.written.append(s)
            except Exception as ex:                            # noqa: BLE001
                print(f"  ⚠️ تعذّرت كتابةُ كاش السورة {s}: {ex}", flush=True)
        return list(self.written)

    def summary(self, all_surahs):
        """ما يُحمل في التقرير ليكون الأثرُ قابلاً للتدقيق."""
        return {"enabled": True, "schema": SCHEMA,
                "reusedSurahs": sorted(self.hits), "heardSurahs": sorted(set(all_surahs) - set(self.hits)),
                "reused": {str(s): v for s, v in sorted(self.hits.items())},
                "notReused": {str(s): v for s, v in sorted(self.misses.items())},
                "codeSha": self.static.get("codeSha"), "modelSha": self.static.get("modelSha")}


def for_run(model_path, *, cl, bucket, source, run_id, env=None, code_roots=CODE_ROOTS):
    """كاشُ التشغيلة، أو None إن أُطفئ أو تعذّر بناءُ مفتاحه (‏الشكُّ ⇒ لا كاش، لا قفزٌ)."""
    env = os.environ if env is None else env
    if disabled(env):
        print("إعادةُ استعمال أحكام الإحصاء: مطفأة (QA_CENSUS_NO_REUSE)", flush=True)
        return None
    try:
        p = Path(model_path)
        if not p.is_file() or p.stat().st_size < 1_000_000:
            raise RuntimeError("ملفُّ النموذج غائبٌ فلا بصمةَ له")
        static = {"codeSha": code_digest(code_roots), "modelSha": file_sha256(p),
                  "facts": runtime_facts(),
                  "env": {k: env.get(k) for k in ENV_KEYS}}
    except Exception as ex:                                    # noqa: BLE001
        print(f"⚠️ لا إعادةَ استعمال: تعذّر بناءُ بصمة التشغيلة ({ex})", flush=True)
        return None
    return CensusCache(cl, bucket, static, write_ok=ci_may_write(source, run_id, env),
                       run_id=run_id)
