"""تنزيل صريح لنموذج القرآن المثبت إلى قرص العداء المؤقت، بلا HF/Actions cache.

لا يُستدعى بوصفه fallback. يجب اختيار allow_download=True صراحة؛ تُحذف
الملفات عند مغادرة السياق، ويُعاد فحص وزنها أيضاً في configure القائم.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from quran_ctc_model import MODEL_ID, REVISION, WEIGHTS_SHA256

WEIGHT_FILE = "model.safetensors"
WEIGHT_LIMIT = 1_500_000_000
METADATA_LIMIT = 1_048_576
DOWNLOAD_DEADLINE = 600
FILES = (
    ("config.json", True), ("vocab.json", True), ("preprocessor_config.json", True),
    ("tokenizer_config.json", False), ("special_tokens_map.json", False),
    ("tokenizer.json", False), (WEIGHT_FILE, True),
)


def checked_public_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not (host in ("huggingface.co", "hf.co")
                    or host.endswith(".huggingface.co") or host.endswith(".hf.co"))):
        raise ValueError("رابط النموذج أو تحويله خارج HTTPS العام المسموح لـHuggingFace")
    return url


class PublicModelRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_file(opener, url, path, *, limit, started, clock=time.monotonic):
    """الحجم والمهلة والبصمة من البايتات الفعلية، مع رفض الاقتطاع وHTTPS downgrade."""
    checked_public_url(url)
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (rafiq-pinned-ephemeral-model/1)",
        "Accept-Encoding": "identity",
    })
    part = path.with_suffix(path.suffix + ".part")
    try:
        with opener.open(request, timeout=60) as response, part.open("xb") as out:
            checked_public_url(response.geturl())
            if response.getcode() != 200 or response.headers.get("Content-Range"):
                raise ValueError("يلزم رد HTTP200 كامل لملف النموذج")
            advertised = response.headers.get("Content-Length")
            advertised = int(advertised) if advertised is not None else None
            if advertised is not None and not 0 <= advertised <= limit:
                raise ValueError("حجم ملف النموذج المعلن يتجاوز السقف")
            digest, size = hashlib.sha256(), 0
            while True:
                if clock() - started > DOWNLOAD_DEADLINE:
                    raise TimeoutError("تجاوز تنزيل النموذج مهلة 600 ثانية")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise ValueError("تجاوزت بايتات ملف النموذج السقف")
                digest.update(chunk)
                out.write(chunk)
            if size == 0 or advertised is not None and size != advertised:
                raise ValueError("ملف نموذج فارغ أو مبتور")
        part.replace(path)
        return {"filename": path.name, "bytes": size, "sha256": digest.hexdigest(), "url": url}
    finally:
        part.unlink(missing_ok=True)


@contextlib.contextmanager
def quran_ephemeral_download(*, allow_download=False, parent=None, opener=None):
    """يعيد بيانات snapshot محلية صالحة طوال السياق فقط؛ لا تنزيل عند غياب الإذن الصريح."""
    if allow_download is not True:
        raise ValueError("يلزم اختيار تنزيل النموذج القرآني المؤقت صراحة؛ لا fallback")
    parent = parent or os.environ.get("RUNNER_TEMP")
    if not parent:
        raise ValueError("يلزم RUNNER_TEMP أو مجلد مؤقت صريح للنموذج")
    parent = Path(parent).resolve()
    cache = Path(os.environ.get("HF_HOME", str(Path.home() / ".cache/huggingface"))).resolve()
    if not parent.is_dir() or parent.is_relative_to(cache):
        raise ValueError("مجلد التنزيل المؤقت غائب أو داخل HF cache")
    maximum = WEIGHT_LIMIT + (len(FILES) - 1) * METADATA_LIMIT
    if shutil.disk_usage(parent).free < maximum + 32 * 1024 * 1024:
        raise ValueError("المساحة المؤقتة لا تكفي سقف النموذج")
    opener = opener or urllib.request.build_opener(PublicModelRedirect())
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="rafiq-quran-model-", dir=parent) as scratch:
        snapshot = Path(scratch)
        evidence = {"id": MODEL_ID, "revision": REVISION, "weightsSha256": WEIGHTS_SHA256,
                    "weightFile": WEIGHT_FILE, "snapshot": str(snapshot),
                    "sourceMode": "explicit-ephemeral-public-download", "cacheWrite": False,
                    "artifactWrite": False, "files": [], "byteLimit": maximum,
                    "deadlineSeconds": DOWNLOAD_DEADLINE}
        for filename, required in FILES:
            url = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{filename}"
            try:
                item = download_file(opener, url, snapshot / filename,
                                     limit=WEIGHT_LIMIT if filename == WEIGHT_FILE else METADATA_LIMIT,
                                     started=started)
            except urllib.error.HTTPError as exc:
                if not required and exc.code == 404:
                    evidence["files"].append({"filename": filename, "optionalAbsent": True})
                    continue
                raise
            if filename == WEIGHT_FILE and item["sha256"] != WEIGHTS_SHA256:
                raise ValueError("بصمة وزن النموذج القرآني المنزّل تخالف البصمة المثبتة")
            evidence["files"].append(item)
        evidence["totalBytes"] = sum(item.get("bytes", 0) for item in evidence["files"])
        evidence["downloadSeconds"] = time.monotonic() - started
        yield evidence
