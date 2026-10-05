#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قياس مصدر صوتي بلا نموذج أو دلو أو إعادة نشر للصوت؛ المخرج في السجل فقط."""
from __future__ import annotations

import argparse
import array
import hashlib
import html
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone

MAX_SOURCES = 10
MAX_BYTES = 200 * 1024 * 1024
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_INPUT_BYTES = 32 * 1024
SAMPLE_RATE = 16000
WINDOW_SAMPLES = 1600  # دقة الصمت 100 م.ث؛ الحدود معلنة في التقرير.
SILENCE_DBFS = -50.0
MIN_SILENCE_SECONDS = 15.0
MAX_PCM_SECONDS = 4 * 3600
RUN_SECONDS = 900
BEGIN = "BEGIN_SOURCE_METADATA_JSON"
END = "END_SOURCE_METADATA_JSON"


class ProbeError(Exception):
    """رسالة ثابتة آمنة للسجل؛ لا تحمل استجابة الخادم أو رابطاً موقعاً."""


def safe_url(url: str) -> str:
    """لا تُطبع query أو fragment أو بيانات الدخول حتى في مسار الفشل."""
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        if ":" in host:
            host = "[" + host + "]"
        port = f":{parts.port}" if parts.port and parts.port != 443 else ""
        return urllib.parse.urlunsplit((parts.scheme, host + port, parts.path, "", ""))
    except (ValueError, TypeError):
        return "[رابط غير صالح]"


def validate_url(url: str, *, resolve: bool = False) -> str:
    if not isinstance(url, str) or len(url) > 8192 or any(ord(c) < 33 for c in url):
        raise ProbeError("رابط المصدر غير صالح")
    try:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.fragment or parsed.port not in (None, 443)):
            raise ValueError
        host = parsed.hostname
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host:
                raise ValueError
        else:
            if not ip.is_global:
                raise ValueError
        if resolve:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
                raise ValueError
    except (ValueError, OSError):
        raise ProbeError("المصدر يجب أن يكون رابط HTTPS عاماً بلا بيانات دخول") from None
    return url


class NoAutomaticRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # المتابعة الافتراضية تقرأ جسم 302 كله في الذاكرة قبل Location.
        # رفضها هنا يحول الرد إلى HTTPError، ونتبعه يدوياً بلا قراءة الجسم.
        return None


def public_opener():
    return urllib.request.build_opener(NoAutomaticRedirect())


def open_response(url: str, *, deadline: float, opener):
    for attempt in range(6):
        validate_url(url, resolve=True)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeError("انتهت مهلة التنزيل")
        request = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (rafiq-source-metadata/1)", "Accept-Encoding": "identity"})
        try:
            return opener.open(request, timeout=min(20, remaining))
        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                raise
            location = exc.headers.get("Location")
            exc.close()  # لا تنزيل لجسم التحويل، ولا يحتفظ السجل بالرابط الموقّع.
            if not location or attempt == 5:
                raise ProbeError("تحويلات المصدر غير مكتملة أو تجاوزت الحد") from None
            url = urllib.parse.urljoin(url, location)
    raise ProbeError("تحويلات المصدر تجاوزت الحد")


@contextmanager
def download_deadline(deadline: float):
    """المشغل Linux: مؤقت يشمل DNS والرؤوس والتحويلات والقراءة المحجوبة."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProbeError("انتهت مهلة التنزيل")

    def expired(_signum, _frame):
        raise ProbeError("انتهت مهلة التنزيل")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if previous_timer != (0.0, 0.0):
        raise ProbeError("يوجد مؤقت متزامن يمنع ضمان مهلة التنزيل")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def fetch(url: str, output: Path, *, limit: int = MAX_BYTES,
          deadline: float | None = None, opener=None) -> dict:
    deadline = min(deadline or math.inf, time.monotonic() + 90)
    with download_deadline(deadline):
        return _fetch(url, output, limit=limit, deadline=deadline, opener=opener)


def _fetch(url: str, output: Path, *, limit: int, deadline: float, opener=None) -> dict:
    digest, size = hashlib.sha256(), 0
    try:
        with open_response(url, deadline=deadline, opener=opener or public_opener()) as response:
            if response.status != 200 or response.headers.get("Content-Range") is not None:
                raise ProbeError("رد المصدر ليس تنزيلاً كاملاً؛ تُرفض الاستجابة الجزئية")
            final_url = response.geturl()
            validate_url(final_url, resolve=True)
            announced = response.headers.get("Content-Length")
            if announced and announced.isdigit() and int(announced) > limit:
                raise ProbeError("حجم التنزيل المعلن يتجاوز الحد")
            with output.open("wb") as stream:
                while True:
                    if time.monotonic() > deadline:
                        raise ProbeError("انتهت مهلة التنزيل")
                    # read1 يعود بعد قراءة socket واحدة؛ read قد ينتظر ملء 64KiB
                    # مع قطرة بيانات كل ثوانٍ، فيؤخر مراجعة المهلة دون حد كافٍ.
                    block = response.read1(min(65536, limit - size + 1))
                    if not block:
                        break
                    size += len(block)
                    if size > limit:
                        raise ProbeError("حجم التنزيل الفعلي يتجاوز الحد")
                    digest.update(block)
                    stream.write(block)
            if not size:
                raise ProbeError("المصدر فارغ")
            if announced and announced.isdigit() and size != int(announced):
                raise ProbeError("التنزيل مبتور قياساً إلى الحجم المعلن")
            return {"bytes": size, "sha256": digest.hexdigest(),
                    "finalUrl": safe_url(final_url)}
    except urllib.error.HTTPError as exc:
        # لا إعادة محاولة ولا تجاوز لرفض الناشر، ولا طباعة للـ URL من الاستثناء.
        raise ProbeError(f"رفض الناشر التنزيل: HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProbeError("تعذر التنزيل أو انتهت مهلة الاتصال") from None


def midad_audio_url(page: bytes) -> str:
    """نقرأ contentUrl المنشور فقط؛ لا تخمين لمسار ولا تجاوز حماية الخادم."""
    decoded = page.decode("utf-8", errors="replace")
    candidates = set()
    for match in re.finditer(r'"contentUrl"\s*:\s*("(?:[^"\\]|\\.)*")', decoded):
        try:
            value = html.unescape(json.loads(match.group(1)))
            candidates.add(validate_url(value))
        except (ValueError, ProbeError):
            continue
    if len(candidates) != 1:
        raise ProbeError("لم تُعط صفحة الناشر contentUrl واحداً واضحاً")
    return candidates.pop()


class PCMStats:
    def __init__(self):
        self.digest = hashlib.sha256()
        self.pending = bytearray()
        self.samples = self.sum_squares = self.peak = 0
        self.silent_start = None
        self.silence_count = 0
        self.silence_samples = 0
        self.first_silences = []
        self.last_silences = deque(maxlen=32)
        self.active_windows = 0

    def _silence_end(self, end):
        if self.silent_start is not None:
            length = end - self.silent_start
            if length > MIN_SILENCE_SECONDS * SAMPLE_RATE:
                interval = {"startSeconds": self.silent_start / SAMPLE_RATE,
                            "endSeconds": end / SAMPLE_RATE, "durationSeconds": length / SAMPLE_RATE}
                self.silence_count += 1
                self.silence_samples += length
                if len(self.first_silences) < 32:
                    self.first_silences.append(interval)
                else:
                    self.last_silences.append(interval)
            self.silent_start = None

    def _window(self, block):
        values = array.array("h", block)
        if sys.byteorder != "little":
            values.byteswap()
        square_sum = sum(value * value for value in values)
        peak = max((abs(value) for value in values), default=0)
        is_silent = square_sum <= len(values) * (32768 * 10 ** (SILENCE_DBFS / 20)) ** 2
        if is_silent:
            if self.silent_start is None:
                self.silent_start = self.samples
        else:
            self.active_windows += 1
            self._silence_end(self.samples)
        self.samples += len(values)
        self.sum_squares += square_sum
        self.peak = max(self.peak, peak)

    def feed(self, block: bytes):
        if (self.samples * 2 + len(self.pending) + len(block)) > MAX_PCM_SECONDS * SAMPLE_RATE * 2:
            raise ProbeError("الصوت المفكوك تجاوز حد المدة")
        self.digest.update(block)
        self.pending.extend(block)
        size = WINDOW_SAMPLES * 2
        while len(self.pending) >= size:
            self._window(self.pending[:size])
            del self.pending[:size]

    def finish(self):
        if len(self.pending) % 2:
            raise ProbeError("خرج PCM مبتور")
        if self.pending:
            self._window(self.pending)
            self.pending.clear()
        if not self.samples:
            raise ProbeError("لم ينتج فك الترميز عينات صوت")
        self._silence_end(self.samples)
        rms = math.sqrt(self.sum_squares / self.samples) / 32768
        intervals = self.first_silences + list(self.last_silences)
        return {"format": "s16le", "sampleRateHz": SAMPLE_RATE, "channels": 1,
                "samples": self.samples, "bytes": self.samples * 2,
                "durationSeconds": self.samples / SAMPLE_RATE, "sha256": self.digest.hexdigest(),
                "rms": rms, "rmsDbfs": 20 * math.log10(rms) if rms else None,
                "peak": self.peak / 32768, "hasSignalAboveThreshold": self.active_windows > 0,
                "silenceThresholdDbfs": SILENCE_DBFS, "windowSeconds": WINDOW_SAMPLES / SAMPLE_RATE,
                "silenceMinimumExclusiveSeconds": MIN_SILENCE_SECONDS,
                "longSilenceCount": self.silence_count,
                "longSilenceTotalSeconds": self.silence_samples / SAMPLE_RATE,
                "longSilences": intervals,
                "omittedSilenceIntervals": self.silence_count - len(intervals)}


class StereoPCMStats:
    """قياس قناتين أصليتين؛ المتوسط الحسابي تشخيص عددي ولا يُكتب كصوت."""
    def __init__(self):
        self.digest = hashlib.sha256()
        self.pending = bytearray()
        self.left = PCMStats()
        self.right = PCMStats()
        self.frames = self.left_sum = self.right_sum = self.cross_sum = 0

    def feed(self, block: bytes):
        if self.frames * 4 + len(self.pending) + len(block) > MAX_PCM_SECONDS * SAMPLE_RATE * 4:
            raise ProbeError("الصوت الثنائي المفكوك تجاوز حد المدة")
        self.digest.update(block)
        self.pending.extend(block)
        size = len(self.pending) // 4 * 4
        if not size:
            return
        values = array.array("h", self.pending[:size])
        del self.pending[:size]
        if sys.byteorder != "little":
            values.byteswap()
        left, right = values[0::2], values[1::2]
        self.frames += len(left)
        self.left_sum += sum(left)
        self.right_sum += sum(right)
        self.cross_sum += sum(lvalue * rvalue for lvalue, rvalue in zip(left, right))
        if sys.byteorder != "little":
            left.byteswap()
            right.byteswap()
        self.left.feed(left.tobytes())
        self.right.feed(right.tobytes())

    def finish(self):
        if self.pending:
            raise ProbeError("خرج PCM الثنائي مبتور عند حد القناتين")
        if not self.frames:
            raise ProbeError("لم ينتج فك القناتين عينات صوت")
        left, right = self.left.finish(), self.right.finish()
        left_power, right_power = self.left.sum_squares, self.right.sum_squares
        left_variance = self.frames * left_power - self.left_sum ** 2
        right_variance = self.frames * right_power - self.right_sum ** 2
        covariance = self.frames * self.cross_sum - self.left_sum * self.right_sum
        correlation = (max(-1.0, min(1.0, covariance / math.sqrt(left_variance * right_variance)))
                       if left_variance > 0 and right_variance > 0 else None)
        mix_power = (left_power + right_power + 2 * self.cross_sum) / 4
        channel_power = (left_power + right_power) / 2
        mix_rms = math.sqrt(max(0, mix_power) / self.frames) / 32768
        ratio = math.sqrt(max(0, mix_power) / channel_power) if channel_power else None
        attenuation = 20 * math.log10(ratio) if ratio and ratio > 0 else None
        # الصفر الدقيق يُعلن صراحة؛ null لا يعني سالباً لانهائياً ولا دليلاً على صمت المصدر.
        exact_cancellation = channel_power > 0 and mix_power == 0
        both_have_energy = all((part["rmsDbfs"] is not None and part["rmsDbfs"] > SILENCE_DBFS)
                               for part in (left, right))
        suspected = (both_have_energy and correlation is not None and correlation <= -0.95
                     and (exact_cancellation or attenuation is not None and attenuation <= -20))
        return {"evaluated": True, "format": "s16le", "sampleRateHz": SAMPLE_RATE,
                "channels": 2, "frames": self.frames, "bytes": self.frames * 4,
                "durationSeconds": self.frames / SAMPLE_RATE, "sha256": self.digest.hexdigest(),
                "left": left, "right": right, "correlationLR": correlation,
                "correlationMethod": "Pearson-full-recording-mean-centered",
                "arithmeticMeanRms": mix_rms, "arithmeticMeanToChannelRmsRatio": ratio,
                "arithmeticMeanAttenuationDb": attenuation,
                "arithmeticMeanExactlyZeroWithChannelEnergy": exact_cancellation,
                "phaseCancellationSuspected": suspected,
                "phaseCancellationCriteria": {"maximumCorrelation": -0.95,
                    "maximumMeanAttenuationDb": -20, "minimumEachChannelRmsDbfs": SILENCE_DBFS},
                "signalIdentityCertified": False}


def _decode_pcm(path: Path, stats, *, channel_arguments: list[str], deadline: float | None = None) -> dict:
    deadline = min(deadline or math.inf, time.monotonic() + 120)
    command = ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
               "-i", str(path), "-map", "0:a:0", "-vn", *channel_arguments, "-ar", str(SAMPLE_RATE),
               "-f", "s16le", "pipe:1"]
    # stderr معزول: قد يضم عنواناً داخل ملف خبيث، ولا نطبع نصه حتى عند الفشل.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    if time.monotonic() > deadline:
                        raise ProbeError("انتهت مهلة فك الصوت")
                    if not selector.select(timeout=min(1, max(0, deadline - time.monotonic()))):
                        continue
                    block = os.read(process.stdout.fileno(), 65536)
                    if not block:
                        break
                    stats.feed(block)
            if process.wait(timeout=max(0.1, deadline - time.monotonic())) != 0:
                raise ProbeError("فشل فك الصوت؛ لم يُعتمد القياس الجزئي")
            if errors.tell() != 0:
                raise ProbeError("أبلغ ffmpeg عن أخطاء؛ لم يُعتمد PCM الجزئي ولو أعاد نجاحاً")
        except subprocess.TimeoutExpired:
            raise ProbeError("انتهت مهلة فك الصوت") from None
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()
    result = stats.finish()
    result["decodedWithoutErrors"] = True
    return result


def decode_audio(path: Path, *, deadline: float | None = None) -> dict:
    return _decode_pcm(path, PCMStats(), channel_arguments=["-ac", "1"], deadline=deadline)


def decode_stereo(path: Path, *, metadata: dict | None = None, deadline: float | None = None) -> dict:
    metadata = metadata if metadata is not None else container_metadata(path, deadline=deadline)
    streams = metadata.get("audioStreams", [])
    channels = streams[0].get("channels") if streams else None
    if channels != 2:
        return {"evaluated": False, "nativeChannels": channels,
                "reason": "قياس L/R يتطلب قناتين أصليتين؛ لم تُنشأ قناتان اصطناعيتان"}
    # لا -ac هنا: نبقي عدد القناتين الأصليتين وترتيبهما، بلا downmix أو upmix.
    result = _decode_pcm(path, StereoPCMStats(), channel_arguments=[], deadline=deadline)
    result["nativeChannels"] = channels
    result["nativeChannelLayout"] = streams[0].get("channel_layout")
    result["channelOrder"] = "first-and-second-native-channel"
    return result


def container_metadata(path: Path, *, deadline: float | None = None) -> dict:
    remaining = min(20, (deadline if deadline is not None else math.inf) - time.monotonic())
    if remaining <= 0:
        raise ProbeError("انتهت مهلة قياس حاوية الصوت")
    try:
        run = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-show_entries", "format=duration:stream=codec_type,codec_name,sample_rate,channels,channel_layout,duration",
            "-of", "json", str(path)], capture_output=True, timeout=remaining, check=False)
        if run.returncode:
            raise ProbeError("فشل ffprobe")
        raw = json.loads(run.stdout)
        duration = float(raw.get("format", {}).get("duration", "nan"))
        audio = [stream for stream in raw.get("streams", []) if stream.get("codec_type") == "audio"]
        return {"durationSeconds": duration if math.isfinite(duration) and duration >= 0 else None,
                "audioStreams": [{key: stream[key] for key in ("codec_name", "sample_rate", "channels", "channel_layout")
                                  if key in stream} for stream in audio]}
    except (subprocess.TimeoutExpired, OSError, ValueError, TypeError):
        raise ProbeError("تعذر قياس حاوية الصوت") from None


def decoder_version() -> str | None:
    try:
        run = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=False)
        return run.stdout.decode("utf-8", errors="replace").splitlines()[0][:200] if run.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def validate_sources(value) -> list[dict]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_SOURCES:
        raise ProbeError("المدخل قائمة من مصدر واحد إلى عشرة مصادر")
    ids = set()
    allowed = {"id", "surah", "riwaya", "url", "identity", "identitySourceUrl"}
    for item in value:
        if not isinstance(item, dict) or set(item) - allowed:
            raise ProbeError("حقول وصف المصدر غير صالحة")
        for key in ("id", "riwaya"):
            if not isinstance(item.get(key), str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", item[key]):
                raise ProbeError("هوية المصدر والرواية يجب أن تكونا معرفين صريحين")
        if item["id"] in ids:
            raise ProbeError("معرف المصدر مكرر")
        ids.add(item["id"])
        if type(item.get("surah")) is not int or not 1 <= item["surah"] <= 114:
            raise ProbeError("رقم السورة خارج المجال")
        validate_url(item.get("url"))
        if "identitySourceUrl" in item:
            validate_url(item["identitySourceUrl"])
        identity = item.get("identity", "")
        if not isinstance(identity, str) or len(identity) > 160 or "://" in identity or any(ord(c) < 32 for c in identity):
            raise ProbeError("بيان هوية القارئ غير صالح")
    return value


def probe_source(source: dict, *, deadline: float) -> dict:
    result = {key: source[key] for key in ("id", "surah", "riwaya")}
    result.update({"requestedUrl": safe_url(source["url"]), "identityVerified": False})
    if source.get("identity"):
        result["declaredIdentity"] = source["identity"]
    if source.get("identitySourceUrl"):
        result["identitySourceUrl"] = safe_url(source["identitySourceUrl"])
    try:
        with tempfile.TemporaryDirectory(prefix="rafiq-source-metadata-") as directory:
            temp = Path(directory)
            url = source["url"]
            parsed = urllib.parse.urlsplit(url)
            if parsed.hostname in ("midad.com", "www.midad.com") and re.fullmatch(r"/recitation/\d+/?", parsed.path):
                result["publisherPage"] = fetch(url, temp / "page", limit=MAX_PAGE_BYTES, deadline=deadline)
                url = midad_audio_url((temp / "page").read_bytes())
                result["resolutionMethod"] = "publisher-contentUrl"
            result["file"] = fetch(url, temp / "source", deadline=deadline)
            result["container"] = container_metadata(temp / "source", deadline=deadline)
            audio_deadline = min(deadline, time.monotonic() + 120)
            decode_errors = []
            for field, decoder in (("pcm", decode_audio), ("stereo", decode_stereo)):
                try:
                    options = {"metadata": result["container"]} if field == "stereo" else {}
                    result[field] = decoder(temp / "source", deadline=audio_deadline, **options)
                except ProbeError as exc:
                    # محاولة كل قياس مستقلة؛ نجاح أحدهما لا يخفي فشل الآخر.
                    result[field] = {"decodedWithoutErrors": False, "error": str(exc)}
                    decode_errors.append(field)
            if decode_errors:
                result["decodeErrors"] = decode_errors
                raise ProbeError("تعذر اعتماد كل قياسات الصوت؛ بقيت أخطاء فك معلنة")
            if result["stereo"].get("evaluated") and result["stereo"]["frames"] != result["pcm"]["samples"]:
                raise ProbeError("اختلف عدد الإطارات بين قياس mono والقناتين؛ لا يُعتمد التشخيص")
            advertised = result["container"]["durationSeconds"]
            result["durationDifferenceSeconds"] = (result["pcm"]["durationSeconds"] - advertised
                                                    if advertised is not None else None)
            result["ok"] = True
    except ProbeError as exc:
        result.update({"ok": False, "error": str(exc)})
    except Exception as exc:
        # اسم الصنف فقط؛ رسائل الشبكة والملفات قد تحتوي query خاصاً.
        result.update({"ok": False, "error": "فشل القياس", "errorType": type(exc).__name__})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources-file", type=Path, help="ملف JSON محلي؛ الافتراضي inputs.sources من حدث GitHub")
    args = parser.parse_args(argv)
    report = {"schema": 2, "tool": "rafiq-source-metadata-2",
              "generatedAt": datetime.now(timezone.utc).isoformat(), "readOnly": True,
              "identityAndVerseCoverageCertified": False, "decoderVersion": decoder_version(), "sources": []}
    try:
        if args.sources_file:
            with args.sources_file.open("rb") as stream:
                raw = stream.read(MAX_INPUT_BYTES + 1)
            if len(raw) > MAX_INPUT_BYTES:
                raise ProbeError("قائمة المصادر أكبر من الحد")
            sources = json.loads(raw)
        else:
            with Path(os.environ["GITHUB_EVENT_PATH"]).open("rb") as stream:
                event = json.load(stream)
            raw = event["inputs"]["sources"]
            if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
                raise ProbeError("قائمة المصادر أكبر من الحد")
            sources = json.loads(raw)
        sources = validate_sources(sources)
        deadline = time.monotonic() + RUN_SECONDS
        for source in sources:
            if time.monotonic() >= deadline:
                report["sources"].append({"id": source["id"], "ok": False, "error": "انتهت مهلة الدفعة"})
                continue
            report["sources"].append(probe_source(source, deadline=deadline))
        report["complete"] = all(source["ok"] for source in report["sources"])
    except ProbeError as exc:
        report.update({"complete": False, "error": str(exc)})
    except Exception as exc:
        report.update({"complete": False, "error": "تعذرت قراءة قائمة المصادر", "errorType": type(exc).__name__})
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(BEGIN)
    print(payload)
    print(END)
    print("REPORT_SHA256=" + hashlib.sha256(payload.encode("utf-8")).hexdigest())
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
