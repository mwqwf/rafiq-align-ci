# -*- coding: utf-8 -*-
"""التوقيتات الكلمية لقراء **ملف لكل آية** (الدوسري/ياسين/everyayah) — بلا فهرس حدود.

كل آية ملف مستقل يبدأ من الصفر، فكل آية HIGH **بالبناء** ولا يلزم محاذاة حدود.
لكن عدة الدمج والتحقق (merge_parts / verify_against_index) تبرهن ضد «فهرس آيات»
بمدى لكل آية وبصمة ثابتة، فنبني أولاً **فهرساً اصطناعياً** من مدد الملفات نفسها
(`index`) ونجمّد بصمته، ثم نولّد الكلمات ضده (`words`) بالمولّد نفسه والحُرّاس
نفسها. الأزمنة **نسبية لملف الآية** (`timeBase: PER_FILE`).

python build_perfile.py index --riwaya warsh --reciter dosary \\
    --audio-base "https://…/audio/warsh/dosary/{surah:03d}{ayah:03d}.mp3" [--surahs 1-114]
python build_perfile.py words --riwaya warsh --reciter dosary --index work/timings_perfile_dosary.jz \\
    --audio-base … --surahs 78-114 --part-id 30

⛔ الصوت يبقى على القرص بين المرحلتين (خادم واسع القرص) ويُحذف بـ`--purge` بعد الدمج.
"""
import argparse
import hashlib
import os
import sys
import time
import wave

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _V2)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from common import load_index, load_text, read_jz, to_wav16k, write_jz  # noqa: E402
from vad import silences  # noqa: E402

import build_index as B  # noqa: E402
from generate import ayah_word_times  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

INDEX_ENGINE = "perfile-index-1.0"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _wav_ms(path):
    with wave.open(path, "rb") as w:
        return int(w.getnframes() * 1000 / w.getframerate())


def ayah_files(args, sn, an):
    mp3 = os.path.join(args.audio_dir, "%03d%03d.mp3" % (sn, an))
    if not (os.path.exists(mp3) and os.path.getsize(mp3) > 1000):
        B.fetch_verified(args.audio_base.format(surah=sn, ayah=an), mp3, log=print)
    return mp3, to_wav16k(mp3)


def cmd_index(args, idx, counts):
    """فهرس اصطناعي: لكل آية ملف — startMs=0، endMs=آخر كلام (قبل الصمت الذيلي)، HIGH."""
    entries, fails = [], []
    t0 = time.time()
    for sn in args.surah_list:
        for an in range(1, counts[sn] + 1):
            aid = "%d:%d" % (sn, an)
            try:
                mp3, wav = ayah_files(args, sn, an)
                dur = _wav_ms(wav)
                sil = silences(wav, min_silence_ms=100)
                end = dur
                if sil and sil[-1][1] >= dur - 40:        # صمت ذيلي حتى نهاية الملف
                    end = max(sil[-1][0], 1)
                entries.append({"ayahId": aid, "startMs": 0, "endMs": end, "fileMs": dur,
                                "conf": 1.0, "confBand": "HIGH", "snapped": True,
                                "fileRef": args.audio_base.format(surah=sn, ayah=an),
                                "sha256": _sha(mp3)})
            except Exception as ex:
                fails.append((aid, type(ex).__name__))
        print("سورة %d: %d آية · فشل %d · %ds" % (sn, counts[sn], len(fails), time.time() - t0),
              flush=True)
    doc = {"schema": 1, "riwaya": args.riwaya, "reciterId": args.reciter,
           "engineVersion": INDEX_ENGINE, "mode": "PER_FILE",
           "source": "AYAH_FILES", "counting": "KUFI",
           "generatedAt": int(time.time() * 1000),
           "notes": "فهرس اصطناعي لقارئ آية-بآية: كل آية ملف، startMs=0، endMs=آخر كلام؛ "
                    "HIGH بالبناء. يُجمَّد بصمةً كما فهرس الحدود.",
           "entries": entries}
    write_jz(args.index, doc)
    print("\nكُتب %s — %d آية · فشل %d %s · sha256 %s"
          % (args.index, len(entries), len(fails), fails[:5], _sha(args.index)[:16]))


def cmd_words(args, ti, text, starts):
    if args.part_id:
        d, base = os.path.split(args.out)
        stem = base[:-3] if base.endswith(".jz") else base
        args.out = os.path.join(d, "parts", "%s.part%s.jz" % (stem, args.part_id))
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
    only = set(args.surah_list)
    done = {}
    if os.path.exists(args.out):
        try:
            done = {e["ayahId"]: e for e in read_jz(args.out).get("entries", [])}
            print("استئناف: %d آية" % len(done), flush=True)
        except Exception:
            pass
    out = list(done.values())
    stats = {"ayahs": 0, "withWords": 0, "words": 0, "dropped": {}}
    by = {}
    for e in ti["entries"]:
        sn = int(e["ayahId"].split(":")[0])
        if sn in only and e["ayahId"] not in done and e.get("confBand") == "HIGH":
            by.setdefault(sn, []).append(e)
    for sn in sorted(by):
        added = 0
        for e in by[sn]:
            stats["ayahs"] += 1
            an = int(e["ayahId"].split(":")[1])
            raw = text[starts[sn] + an - 1]
            try:
                _, wav = ayah_files(args, sn, an)
                sil = silences(wav, min_silence_ms=80)
                onset = sil[0][1] if sil and sil[0][0] == 0 else 0
                words, meta = ayah_word_times(
                    wav, e["startMs"], e["endMs"], raw,
                    "pf_%s_%s_%03d_%03d" % (args.riwaya, args.reciter, sn, an), onset_ms=onset)
            except Exception as ex:
                print("    ⚠️ %s سقطت باستثناء: %s" % (e["ayahId"], type(ex).__name__), flush=True)
                stats["dropped"]["exception"] = stats["dropped"].get("exception", 0) + 1
                continue
            if not words:
                r = meta["reason"]
                stats["dropped"][r] = stats["dropped"].get(r, 0) + 1
                continue
            if len(words) != len(raw.split()):
                stats["dropped"]["token-count"] = stats["dropped"].get("token-count", 0) + 1
                continue
            added += 1
            stats["words"] += len(words)
            out.append({
                "ayahId": e["ayahId"],
                "evidence": {"n": meta["n"], "matched": meta["matched"],
                             "exact": meta.get("exact", 0), "acc": meta["acc"],
                             "interp": meta["interp"],
                             "interpSpeech": meta.get("interpSpeech", meta["interp"]),
                             "fullEvidence": bool(meta.get("fullEvidence", False)),
                             "zeroLen": meta.get("zeroLen", 0)},
                "words": [{"wordId": "%s:%d" % (e["ayahId"], w["subIndex"] + 1),
                           "subIndex": w["subIndex"],
                           "startMs": w["startMs"], "endMs": w["endMs"],
                           "conf": round(e["conf"] * (0.7 if w["interpolated"] else 0.95), 3)}
                          for w in words]})
        stats["withWords"] += added
        print("سورة %d: +%d/%d (الإجمالي %d)" % (sn, added, len(by[sn]), len(out)), flush=True)
        B.write_doc(args, ti, out)          # 💾 بعد كل سورة
    B.write_doc(args, ti, out)
    print("\nالمخرج: %d آية · %d كلمة ← %s" % (len(out), sum(len(e["words"]) for e in out), args.out))
    print("ساقطة: %s" % stats["dropped"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["index", "words"])
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--audio-base", dest="audio_base", required=True,
                    help="قالب فيه {surah:03d}{ayah:03d}")
    ap.add_argument("--index", default=None, help="الفهرس الاصطناعي (يُكتب في index ويُقرأ في words)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--surahs", default="1-114")
    ap.add_argument("--part-id", dest="part_id", default=None)
    ap.add_argument("--audio-dir", dest="audio_dir", default=None)
    args = ap.parse_args()
    args.time_base = "PER_FILE"
    args.audio_dir = args.audio_dir or os.path.join(_HERE, "work", "audio_" + args.reciter)
    args.index = args.index or os.path.join(_HERE, "work", "timings_perfile_%s.jz" % args.reciter)
    args.out = args.out or os.path.join(_V2, "out", "wordtimings_%s.jz" % args.reciter)
    os.makedirs(args.audio_dir, exist_ok=True)
    idx = load_index()
    counts = {s["n"]: s["ayahs"] for s in idx["surahs"]}
    starts = {s["n"]: s["start"] for s in idx["surahs"]}
    args.surah_list = sorted(B.parse_range(args.surahs) or range(1, 115))
    if args.cmd == "index":
        cmd_index(args, idx, counts)
    else:
        ti = read_jz(args.index)
        if ti.get("mode") != "PER_FILE":
            print("⛔ الفهرس ليس اصطناعياً PER_FILE")
            return 2
        cmd_words(args, ti, load_text(args.riwaya), starts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
