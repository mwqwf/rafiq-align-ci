#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حدود التنزيل وخصوصية الروابط وقياس صوت اصطناعي؛ لا ملف قرآن في الاختبارات."""
from __future__ import annotations

import array
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
import urllib.error
import wave
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from tools.ci_fleet import source_metadata_probe as probe


def pcm(seconds, *, signal=False):
    count = round(seconds * probe.SAMPLE_RATE)
    values = array.array("h", (round(10000 * math.sin(2 * math.pi * 440 * n / probe.SAMPLE_RATE))
                              if signal else 0 for n in range(count)))
    if sys.byteorder != "little":
        values.byteswap()
    return values.tobytes()


def save_wav(path, samples):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(probe.SAMPLE_RATE)
        output.writeframes(samples)


class Response(io.BytesIO):
    def __init__(self, data, *, length=None, url="https://audio.example/test.wav?signature=PRIVATE"):
        super().__init__(data)
        self.headers = {"Content-Length": str(length)} if length is not None else {}
        self.url = url

    def geturl(self):
        return self.url


class MetadataTests(unittest.TestCase):
    def test_generated_wav_proves_actual_duration_pcm_hash_and_long_silence(self):
        self.assertIsNotNone(shutil.which("ffmpeg"), "الاختبار يتطلب ffmpeg")
        self.assertIsNotNone(shutil.which("ffprobe"), "الاختبار يتطلب ffprobe")
        samples = pcm(1, signal=True) + pcm(18) + pcm(1, signal=True)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.wav"
            save_wav(path, samples)
            metadata = probe.container_metadata(path)
            actual = probe.decode_audio(path)
        self.assertEqual(metadata["durationSeconds"], 20)
        self.assertEqual(actual["durationSeconds"], 20)
        self.assertEqual(actual["sha256"], hashlib.sha256(samples).hexdigest())
        self.assertEqual(actual["samples"], 320000)
        self.assertTrue(actual["decodedWithoutErrors"])
        self.assertTrue(actual["hasSignalAboveThreshold"])
        self.assertEqual(actual["longSilences"], [{"startSeconds": 1, "endSeconds": 19, "durationSeconds": 18}])
        self.assertAlmostEqual(actual["peak"], 10000 / 32768)
        self.assertAlmostEqual(actual["rms"], (10000 / 32768) * math.sqrt(0.05), places=4)

    def test_exact_fifteen_seconds_is_not_long_and_partial_tail_is_counted(self):
        for seconds, count in ((15, 0), (15.05, 1)):
            with self.subTest(seconds=seconds):
                stats = probe.PCMStats()
                raw = pcm(seconds)
                for offset in range(0, len(raw), 777):  # لا نفترض حدود قراءة ffmpeg.
                    stats.feed(raw[offset:offset + 777])
                result = stats.finish()
                self.assertEqual(result["longSilenceCount"], count)
                self.assertEqual(result["durationSeconds"], seconds)
                self.assertFalse(result["hasSignalAboveThreshold"])
                self.assertIsNone(result["rmsDbfs"])
                self.assertEqual(result["sha256"], hashlib.sha256(raw).hexdigest())

    def test_odd_pcm_or_empty_stream_is_rejected(self):
        for raw in (b"", b"x"):
            stats = probe.PCMStats()
            stats.feed(raw)
            with self.assertRaises(probe.ProbeError):
                stats.finish()

    def test_silence_report_size_is_bounded_without_hiding_omission_count(self):
        stats = probe.PCMStats()
        # حدود الصمت نفسها؛ نقص العتبة هنا لتجربة 70 فترة بلا ملف كبير.
        with patch.object(probe, "MIN_SILENCE_SECONDS", 0.01):
            for _ in range(70):
                stats.feed(pcm(0.1) + pcm(0.1, signal=True))
            result = stats.finish()
        self.assertEqual(result["longSilenceCount"], 70)
        self.assertEqual(len(result["longSilences"]), 64)
        self.assertEqual(result["omittedSilenceIntervals"], 6)
        self.assertAlmostEqual(result["longSilenceTotalSeconds"], 7)
        self.assertEqual(result["longSilences"][-1]["startSeconds"], 13.8)

    def test_decoded_duration_limit_and_decoder_deadline_are_enforced(self):
        with patch.object(probe, "MAX_PCM_SECONDS", 0.1):
            with self.assertRaises(probe.ProbeError):
                probe.PCMStats().feed(pcm(0.11))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.wav"
            save_wav(path, pcm(1))
            started = time.monotonic()
            with self.assertRaisesRegex(probe.ProbeError, "مهلة"):
                probe.decode_audio(path, deadline=started - 1)
            self.assertLess(time.monotonic() - started, 5)

    def test_decoder_failure_does_not_return_partial_certification(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.wav"
            path.write_bytes(b"not an audio file https://example.test/?token=PRIVATE")
            with self.assertRaises(probe.ProbeError) as caught:
                probe.decode_audio(path)
            self.assertNotIn("PRIVATE", str(caught.exception))

    def test_decoder_success_status_with_error_output_rejects_partial_pcm(self):
        # عملية حقيقية تحاكي decoder يكتب PCM ثم خطأ ويخرج بالرمز 0.
        with tempfile.TemporaryDirectory() as folder:
            shim = Path(folder) / "ffmpeg"
            shim.write_text(f"#!{sys.executable}\nimport os\nos.write(1, bytes(3200))\n"
                            "os.write(2, b'decode error https://audio.example/?token=PRIVATE')\n")
            shim.chmod(0o700)
            with patch.dict(os.environ, {"PATH": folder + os.pathsep + os.environ.get("PATH", "")}):
                with self.assertRaisesRegex(probe.ProbeError, "PCM الجزئي") as caught:
                    probe.decode_audio(Path(folder) / "source.wav")
            self.assertNotIn("PRIVATE", str(caught.exception))

    def test_real_truncated_wav_is_rejected_instead_of_accepting_shortened_pcm(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "truncated.wav"
            save_wav(path, pcm(2, signal=True))
            path.write_bytes(path.read_bytes()[:-probe.SAMPLE_RATE * 2])
            with self.assertRaises(probe.ProbeError):
                probe.decode_audio(path)

    def fetch(self, data, *, length=None, limit=10):
        opener = Mock()
        opener.open.return_value = Response(data, length=length)
        with tempfile.TemporaryDirectory() as folder, patch.object(probe, "validate_url", side_effect=lambda value, **_: value):
            return probe.fetch("https://audio.example/test.wav?token=INPUT", Path(folder) / "audio", limit=limit, opener=opener)

    def test_download_limit_checks_header_and_actual_stream(self):
        for data, length in ((b"tiny", 1000), (b"elevenbytes", None), (b"elevenbytes", 10)):
            with self.subTest(length=length), self.assertRaisesRegex(probe.ProbeError, "حجم"):
                self.fetch(data, length=length)
        result = self.fetch(b"ten-bytes!", length=10)
        self.assertEqual(result["bytes"], 10)
        self.assertEqual(result["sha256"], hashlib.sha256(b"ten-bytes!").hexdigest())
        self.assertEqual(result["finalUrl"], "https://audio.example/test.wav")
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_empty_or_truncated_download_is_not_success(self):
        for data, length in ((b"", None), (b"short", 10)):
            with self.subTest(data=data), self.assertRaises(probe.ProbeError):
                self.fetch(data, length=length)

    def test_403_is_reported_without_retry_or_signed_query(self):
        url = "https://audio.example/source.mp3?token=PRIVATE"
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(url, 403, url, {}, None)
        with tempfile.TemporaryDirectory() as folder, patch.object(probe, "validate_url", side_effect=lambda value, **_: value):
            with self.assertRaises(probe.ProbeError) as caught:
                probe.fetch(url, Path(folder) / "audio", opener=opener)
        self.assertIn("403", str(caught.exception))
        self.assertNotIn("PRIVATE", str(caught.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_download_deadline_is_enforced(self):
        opener = Mock()
        opener.open.return_value = Response(b"bytes")
        with tempfile.TemporaryDirectory() as folder, patch.object(probe, "validate_url", side_effect=lambda value, **_: value):
            with self.assertRaisesRegex(probe.ProbeError, "مهلة"):
                probe.fetch("https://audio.example/file", Path(folder) / "audio",
                            deadline=time.monotonic() - 1, opener=opener)

    def test_deadline_interrupts_blocked_open_not_just_checks_between_reads(self):
        opener = Mock()
        opener.open.side_effect = lambda *_, **__: time.sleep(2)
        started = time.monotonic()
        with tempfile.TemporaryDirectory() as folder, patch.object(probe, "validate_url", side_effect=lambda value, **_: value):
            with self.assertRaisesRegex(probe.ProbeError, "مهلة"):
                probe.fetch("https://audio.example/file", Path(folder) / "audio",
                            deadline=started + 0.05, opener=opener)
        self.assertLess(time.monotonic() - started, 1)

    def test_redirect_body_is_closed_without_download_and_result_query_is_hidden(self):
        body = Mock()
        body.read.side_effect = AssertionError("لا تُقرأ بيانات جسم 302")
        redirect = urllib.error.HTTPError("https://audio.example/old", 302, "redirect", {
            "Location": "https://audio.example/new?token=PRIVATE"}, body)
        opener = Mock()
        opener.open.side_effect = [redirect, Response(b"data", url="https://audio.example/new?token=PRIVATE")]
        with tempfile.TemporaryDirectory() as folder, patch.object(probe, "validate_url", side_effect=lambda value, **_: value):
            result = probe.fetch("https://audio.example/old", Path(folder) / "audio", opener=opener)
        body.read.assert_not_called()
        body.close.assert_called_once()
        self.assertEqual(result["finalUrl"], "https://audio.example/new")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(opener.open.call_count, 2)

    def test_redirects_have_count_limit_and_cannot_downgrade_https(self):
        for destination in ("https://audio.example/again", "http://audio.example/unsafe"):
            opener = Mock()
            opener.open.side_effect = lambda *_, **__: (_ for _ in ()).throw(
                urllib.error.HTTPError("https://audio.example/old", 302, "redirect", {"Location": destination}, io.BytesIO(b"ignored")))
            with tempfile.TemporaryDirectory() as folder, patch.object(probe.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 443))]):
                with self.assertRaises(probe.ProbeError):
                    probe.fetch("https://audio.example/old", Path(folder) / "audio", opener=opener)
            self.assertEqual(opener.open.call_count, 6 if destination.startswith("https:") else 1)

    def test_url_validation_rejects_http_local_targets_and_credentials(self):
        for url in ("http://audio.example/file", "https://localhost/file", "https://127.0.0.1/file",
                    "https://192.168.1.1/file", "https://169.254.169.254/file", "file:///tmp/audio",
                    "https://a:b@audio.example/file", "https://audio.example:444/file", "https://audio.example/file\n"):
            with self.subTest(url=url), self.assertRaises(probe.ProbeError):
                probe.validate_url(url)
        with patch.object(probe.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(probe.ProbeError):
                probe.validate_url("https://audio.example/file", resolve=True)

    def test_publisher_content_url_is_ephemeral_and_ambiguity_fails(self):
        signed = "https://media.example/rec.mp3?token=PRIVATE&expiry=123"
        page = json.dumps({"contentUrl": signed}).encode()
        self.assertEqual(probe.midad_audio_url(page), signed)
        escaped = b'{"contentUrl":"https:\\/\\/media.example\\/rec.mp3?token=PRIVATE&amp;expiry=123"}'
        self.assertEqual(probe.midad_audio_url(escaped), signed)
        with self.assertRaises(probe.ProbeError):
            probe.midad_audio_url(page + b'{"contentUrl":"https://media.example/other.mp3"}')

    def test_source_description_rejects_unknown_fields_or_unbounded_lists(self):
        good = {"id": "peshawa_s63", "riwaya": "hafs", "surah": 63, "url": "https://audio.example/063.mp3"}
        self.assertEqual(probe.validate_sources([good]), [good])
        invalid = [[], [good] * 11, [good, good], [{**good, "surah": True}], [{**good, "surah": 115}],
                   [{**good, "token": "PRIVATE"}], [{**good, "identity": "https://example/?token=PRIVATE"}],
                   [{**good, "id": 123}]]
        for sources in invalid:
            with self.subTest(sources=sources), self.assertRaises(probe.ProbeError):
                probe.validate_sources(sources)

    def test_report_never_prints_query_or_exception_details_and_is_framed(self):
        source = {"id": "sample", "riwaya": "hafs", "surah": 63,
                  "url": "https://audio.example/file.mp3?signature=PRIVATE",
                  "identitySourceUrl": "https://publisher.example/info?token=PRIVATE"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sources.json"
            path.write_text(json.dumps([source]))
            with patch.object(probe, "fetch", side_effect=ValueError("PRIVATE https://bad/?token=PRIVATE")), \
                    redirect_stdout(io.StringIO()) as capture:
                rc = probe.main(["--sources-file", str(path)])
        log = capture.getvalue()
        self.assertEqual(rc, 1)
        self.assertNotIn("PRIVATE", log)
        self.assertNotIn("signature=", log)
        lines = log.splitlines()
        self.assertEqual(lines[0], probe.BEGIN)
        self.assertEqual(lines[2], probe.END)
        self.assertEqual(lines[3], "REPORT_SHA256=" + hashlib.sha256(lines[1].encode()).hexdigest())
        self.assertFalse(json.loads(lines[1])["identityAndVerseCoverageCertified"])

    def test_github_event_read_does_not_need_payload_in_environment(self):
        source = {"id": "sample", "riwaya": "hafs", "surah": 1, "url": "https://audio.example/file"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "event.json"
            path.write_text(json.dumps({"inputs": {"sources": json.dumps([source])}}))
            with patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(path)}), \
                    patch.object(probe, "probe_source", return_value={"id": "sample", "ok": True}) as read, \
                    redirect_stdout(io.StringIO()):
                rc = probe.main([])
        self.assertEqual(rc, 0)
        self.assertEqual(read.call_args.args[0], source)


if __name__ == "__main__":
    unittest.main()
