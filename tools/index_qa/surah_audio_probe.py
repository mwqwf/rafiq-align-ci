#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسبارُ صوتِ سورةٍ في فهرس — قارئٌ محضٌ يحسم «عطبُ المادّة أم عطبُ أداتنا؟».

    python tools/index_qa/surah_audio_probe.py <مفتاح الفهرس> --surahs 10,12 \
        [--also timings-staging/…jz]

لكلّ سورة يطبع **أرقاماً خاماً**:
  • ‏`fileRef` من الفهرس المنشور (‏ومن المرشّح إن أُعطي)، وأوّلَ `startMs` وآخرَ `endMs`.
  • ما يُعلنه الناشر: `Content-Length` في `HEAD`، و`size`/`length` من بيانات archive.org.
  • الحجمَ المنزَّل وبصمتَه (‏تنزيلان يُقارَنان) والمدّةَ المقدّرةَ من الحجم والمعدّل.
  • مدّةَ `mp3dur` بعدّ الإطارات، ومدّةَ `ffprobe`، وطولَ الفكّ الكامل بـffmpeg ونصَّ خطئه.
  • مواضعَ فقدِ التزامن بين الإطارات (‏بالبايت والزمن)، وطاقةَ الصوت بعد آخر ثانيةٍ مفكوكة.

⛔ **لا يكتب في الدلو شيئاً ولا يقرأ سرّاً**: الفهرسُ من الرابط العامّ و`User-Agent`
   المتصفّح (‏`r2.dev` يردّ 403 لـ`Python-urllib`)، والصوتُ من رابط الفهرس نفسِه.
⛔ **ولا يحكم**: الحكمُ لمن يقرأ الأرقام ويقابلها بسورةٍ ضابطةٍ من القارئ نفسِه.
"""
import argparse, gzip, hashlib, json, os, re, shutil, subprocess, sys, tempfile
import urllib.parse, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PUBLIC = os.environ.get("R2_PUBLIC", "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev")
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq tools)"}
sys.path.insert(0, str(Path(__file__).parent))
import mp3dur  # noqa: E402


def http(url, method="GET", timeout=120):
    rq = urllib.request.Request(url, method=method, headers=UA)
    return urllib.request.urlopen(rq, timeout=timeout)


def load_index(key):
    with http(f"{PUBLIC}/{key}") as r:
        raw = r.read()
    return json.loads(gzip.decompress(raw).decode("utf-8")), hashlib.sha256(raw).hexdigest()


def surah_span(idx, s):
    ee = [e for e in idx["entries"] if int(e["ayahId"].split(":")[0]) == s]
    refs = {}
    for e in ee:
        refs.setdefault(e.get("fileRef"), []).append(e)
    return ee, refs


def ia_meta(url):
    """حجمُ الملفّ ومدّتُه كما يُعلنهما archive.org نفسُه (‏إن كان المصدرُ منه)."""
    m = re.match(r"https?://archive\.org/download/([^/]+)/(.+)$", url)
    if not m:
        return None
    ident, name = m.group(1), urllib.parse.unquote(m.group(2))
    try:
        with http(f"https://archive.org/metadata/{ident}/files", timeout=60) as r:
            files = json.loads(r.read().decode("utf-8")).get("result", [])
    except Exception as e:                                # noqa: BLE001
        return f"⛔ {type(e).__name__}: {e}"
    for f in files:
        if f.get("name") == name:
            return {k: f.get(k) for k in ("size", "length", "bitrate", "md5", "format", "mtime")}
    return f"⛔ الاسم غير موجود في بيانات المجلّد ({len(files)} ملفّاً)"


def download(url, dst):
    with http(url, timeout=300) as r, open(dst, "wb") as f:
        want = int(r.headers.get("Content-Length") or 0)
        shutil.copyfileobj(r, f)
    got = os.path.getsize(dst)
    return want, got, hashlib.sha256(open(dst, "rb").read()).hexdigest()


def frame_walk(path):
    """مشيٌ صارمٌ على الإطارات: يتبع طولَ كلّ إطارٍ ويسجّل كلَّ فقدِ تزامن بموضعه."""
    d = open(path, "rb").read()
    i = 0
    if d[:3] == b"ID3":
        i = 10 + ((d[6] & 0x7f) << 21 | (d[7] & 0x7f) << 14 | (d[8] & 0x7f) << 7 | (d[9] & 0x7f))
    t, frames, gaps, brs, last_end, id3_mid = 0.0, 0, [], {}, i, []
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
                    if i != last_end:
                        gaps.append((last_end, i, round(t, 2)))
                    brs[br // 1000] = brs.get(br // 1000, 0) + 1
                    t += spf / sr; frames += 1
                    i += flen; last_end = i
                    continue
        if d[i:i + 3] == b"ID3" and i > 0:
            id3_mid.append((i, round(t, 2)))
        i += 1
    return {"sec": round(t, 3), "frames": frames, "bytes": len(d), "bitrates": brs,
            "gaps": len(gaps), "gap_bytes": sum(b - a for a, b, _ in gaps),
            "first_gaps": gaps[:8], "last_gaps": gaps[-4:], "id3_mid": id3_mid[:4],
            "tail_unframed": len(d) - last_end}


def ensure_ffmpeg():
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True
    if shutil.which("sudo") and shutil.which("apt-get"):
        subprocess.run("sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg >/dev/null",
                       shell=True, check=False)
    return bool(shutil.which("ffmpeg"))


def ff_decode(path, extra=()):
    p = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *extra, "-i", path, "-f", "f32le",
                        "-ac", "1", "-ar", "16000", "pipe:1"], capture_output=True, timeout=1800)
    return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace").strip()


def energy_profile(pcm_bytes, step_s=30):
    """RMS لكلّ مقطع — بايثون خالصاً (‏عدّاءُ الجسر بلا numpy)."""
    import array, math
    x = array.array("f"); x.frombytes(pcm_bytes[:len(pcm_bytes) - len(pcm_bytes) % 4])
    n, out = 16000 * step_s, []
    for k in range(0, len(x), n):
        seg = x[k:k + n:4]
        out.append(round(math.sqrt(sum(v * v for v in seg) / len(seg)), 4) if len(seg) else 0.0)
    return out


def probe(url, work, label):
    print(f"\n  ── {label}: {url}")
    try:
        with http(url, method="HEAD", timeout=60) as r:
            print(f"     HEAD: {r.status} · Content-Length={r.headers.get('Content-Length')}"
                  f" · النهائيّ={r.url}")
    except Exception as e:                                # noqa: BLE001
        print(f"     HEAD ⛔ {type(e).__name__}: {e}")
    print(f"     archive.org يُعلن: {ia_meta(url)}")
    f1, f2 = os.path.join(work, "a.mp3"), os.path.join(work, "b.mp3")
    try:
        w1, g1, h1 = download(url, f1)
        w2, g2, h2 = download(url, f2)
    except Exception as e:                                # noqa: BLE001
        print(f"     تنزيل ⛔ {type(e).__name__}: {e}")
        return
    print(f"     تنزيل1: معلَن {w1} · منزَّل {g1} · {h1[:16]}")
    print(f"     تنزيل2: معلَن {w2} · منزَّل {g2} · {h2[:16]} · {'متطابقان' if h1 == h2 else '⛔ مختلفان'}")
    sec, fr, info, nb = mp3dur.dur(f1)
    print(f"     mp3dur: {sec:.3f}ث · {fr} إطاراً · info={info} · {nb} بايت")
    if info:
        print(f"     المدّةُ من الحجم بمعدّل {info[2]}ك.ب/ث: {nb * 8 / (info[2] * 1000):.1f}ث")
    fw = frame_walk(f1)
    print(f"     مشيُ الإطارات: {json.dumps(fw, ensure_ascii=False)}")
    if not ensure_ffmpeg():
        print("     ⛔ لا ffmpeg")
        return
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration,bit_rate:stream=duration,codec_name,sample_rate,channels",
                        "-of", "json", f1], capture_output=True, text=True)
    print(f"     ffprobe: {p.stdout.strip().replace(chr(10), ' ')} {p.stderr.strip()[:300]}")
    v = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.split("\n")[0]
    print(f"     {v}")
    rc, pcm, err = ff_decode(f1)
    print(f"     فكٌّ كامل: rc={rc} · {len(pcm) / 4 / 16000:.3f}ث · stderr({len(err.splitlines())} سطراً)="
          f"{err[:600]!r}")
    if err:
        print(f"     آخرُ stderr: {err[-400:]!r}")
    # أين يقع الخطأ؟ ‏-v warning مع showinfo زمنيّاً غاليةٌ — فنعدّ الإطارات المفكوكة بـ-debug_ts لا.
    rc2, pcm2, err2 = ff_decode(f1, ("-err_detect", "ignore_err"))
    print(f"     فكٌّ متسامح (قياسٌ فقط): rc={rc2} · {len(pcm2) / 4 / 16000:.3f}ث · stderr={err2[:200]!r}")
    p3 = subprocess.run(["ffmpeg", "-nostdin", "-v", "warning", "-i", f1, "-t", "5", "-f", "null", "-"],
                        capture_output=True, text=True)
    print(f"     أوّلُ 5ث وحدها: stderr={p3.stderr.strip()[:300]!r}")
    p4 = subprocess.run(["ffmpeg", "-nostdin", "-v", "warning", "-ss", "10", "-i", f1, "-f", "null", "-"],
                        capture_output=True, text=True)
    print(f"     من الثانية 10 إلى الآخر: stderr={p4.stderr.strip()[:300]!r}")
    try:
        prof = energy_profile(pcm)
        print(f"     طاقةُ كلّ 30ث (RMS): {prof}")
    except Exception as e:                                # noqa: BLE001
        print(f"     الطاقة ⛔ {e}")
    # ذيلُ الملفّ بعد آخر إطارٍ متّصل: أفيه صوت؟
    if fw["tail_unframed"] > 1000:
        tail = os.path.join(work, "tail.mp3")
        with open(f1, "rb") as fi, open(tail, "wb") as fo:
            fi.seek(fw["bytes"] - fw["tail_unframed"]); fo.write(fi.read())
        rc5, pcm5, err5 = ff_decode(tail)
        print(f"     الذيلُ غيرُ المؤطَّر ({fw['tail_unframed']} بايت) مفكوكاً وحده: "
              f"{len(pcm5) / 4 / 16000:.3f}ث · {err5[:200]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key", help="مفتاح الفهرس المنشور، مثل timings/qalun/x.jz")
    ap.add_argument("--surahs", default="10")
    ap.add_argument("--also", default="", help="مفتاحُ مرشّحٍ يُقرأ للمقارنة (اختياريّ)")
    a = ap.parse_args()
    idx, sha = load_index(a.key)
    print(f"▶ {a.key} · {sha[:16]} · {len(idx['entries'])} مدخلاً")
    cand = None
    if a.also:
        try:
            cand, csha = load_index(a.also)
            print(f"▶ {a.also} · {csha[:16]} · {len(cand['entries'])} مدخلاً")
        except Exception as e:                            # noqa: BLE001
            print(f"▶ {a.also} ⛔ {type(e).__name__}: {e}")
    with tempfile.TemporaryDirectory() as work:
        for s in (int(x) for x in a.surahs.split(",")):
            print(f"\n══ السورة {s}")
            urls = []
            for name, ix in (("المنشور", idx), ("المرشّح", cand)):
                if ix is None:
                    continue
                ee, refs = surah_span(ix, s)
                for ref, es in refs.items():
                    st = min(e["startMs"] for e in es)
                    en = max((e.get("endMs") or 0) for e in es)
                    last = max(es, key=lambda e: e["startMs"])
                    print(f"  {name}: {len(es)} مدخلاً · fileRef={ref}\n"
                          f"     أوّلُ startMs={st} · آخرُ endMs={en} · آخرُ آية {last['ayahId']}"
                          f" ({last['startMs']}..{last.get('endMs')})")
                    if ref and ref not in urls:
                        urls.append(ref)
            for u in urls:
                probe(u, work, f"السورة {s}")


if __name__ == "__main__":
    main()
