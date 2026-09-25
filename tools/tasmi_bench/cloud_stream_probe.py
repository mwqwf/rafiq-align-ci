# -*- coding: utf-8 -*-
"""🩺 مسبارُ صحّةِ التفريغ السحابيّ لـ«سمّع معي» والتسميع (‏/v1/tasmi/stream) — قراءةٌ لحالة الخادم الحيّ.

يسجّل جهازاً مؤقّتاً، ويرسل ثلاثةَ مقاطع قصيرة من تلاوةٍ عامّةٍ منشورة (العفاسي، everyayah)، ويطبع
رمزَ الجواب والنصّ، ثمّ يمحو الجهاز. لا أسرار: العنوانُ علنيٌّ في التطبيق نفسه. الصوتُ لا يُخزَّن في الخادم.
"""
import io, json, subprocess, sys, time, urllib.request, urllib.error, wave

BASE = "https://mushafak-api.mushafak.workers.dev"
CLIPS = ["001002", "002255", "018022"]


def call(method, path, data=None, headers=None, timeout=20):
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.time() - t0
    except Exception as e:  # شبكة/مهلة
        return None, str(e).encode(), time.time() - t0


def wav_clip(ayah, seconds=5.5):
    mp3 = f"/tmp/{ayah}.mp3"
    urllib.request.urlretrieve(f"https://everyayah.com/data/Alafasy_128kbps/{ayah}.mp3", mp3)
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-t", str(seconds), "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(pcm)
    return b.getvalue()


def main():
    import shutil
    if not shutil.which("ffmpeg"):   # صورةُ العدّاد قد تخلو منه
        subprocess.run("sudo apt-get -qq update && sudo apt-get -qq install -y ffmpeg >/dev/null", shell=True)
    s, body, dt = call("GET", "/v1/app/version")
    print(f"GET /v1/app/version → {s} ({dt:.2f}s) {body[:120]!r}")
    s, body, dt = call("POST", "/v1/device", json.dumps({"app_version": "probe", "platform": "ci-probe"}).encode(),
                       {"content-type": "application/json"})
    print(f"POST /v1/device → {s} ({dt:.2f}s)")
    if s != 200:
        print("⛔ تعذّر تسجيلُ جهاز:", body[:200]); return 1
    tok = json.loads(body)["token"]
    auth = {"authorization": f"Bearer {tok}"}
    bad = 0
    try:
        for a in CLIPS:
            s, body, dt = call("POST", "/v1/tasmi/stream", wav_clip(a), {**auth, "content-type": "audio/wav"})
            txt = body.decode("utf-8", "replace")[:200]
            print(f"POST /v1/tasmi/stream {a} → {s} ({dt:.2f}s) {txt}")
            bad += s != 200
    finally:
        s, _, _ = call("DELETE", "/v1/device", headers=auth)
        print(f"DELETE /v1/device → {s}")
    print("الخلاصة:", "سليم" if bad == 0 else f"⛔ {bad}/{len(CLIPS)} مقاطع فشلت")
    return 0


if __name__ == "__main__":
    sys.exit(main())
