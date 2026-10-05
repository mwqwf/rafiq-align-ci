#!/usr/bin/env python3
"""يثبت مرشح الفحص اليدوي المجاني وأصله قبل الصوت؛ لا يكتب إلى الدلو."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/index_qa"))
sys.path.insert(0, str(ROOT / "tools/alignment_v3"))
SHA_RE = re.compile(r"[0-9a-f]{64}")
KEY_RE = re.compile(r"timings-staging/([a-z_]+)/([a-z0-9_]+)\.([0-9a-f]{8})\.jz")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parent_key(key):
    match = KEY_RE.fullmatch(str(key))
    require(match is not None, "يلزم مفتاح staging صريح يحمل بصمة من ثماني خانات")
    return f"timings/{match[1]}/{match[2]}.jz"


def validate_binding(key, sha, parent_sha, blob, parent_blob):
    require(SHA_RE.fullmatch(str(sha)) and SHA_RE.fullmatch(str(parent_sha)),
            "يلزم كامل بصمتي المرشح والأصل")
    target = parent_key(key)
    require(KEY_RE.fullmatch(key)[3] == sha[:8], "لاحقة المفتاح لا تطابق بصمة المرشح")
    require(hashlib.sha256(blob).hexdigest() == sha, "تغيرت بايتات المرشح")
    require(hashlib.sha256(parent_blob).hexdigest() == parent_sha, "تغير الأصل المنشور")
    idx, parent = json.loads(gzip.decompress(blob)), json.loads(gzip.decompress(parent_blob))
    identity = tuple(KEY_RE.fullmatch(key).group(i) for i in (1, 2))
    for doc in (idx, parent):
        require((doc.get("riwaya"), doc.get("reciterId")) == identity,
                "هوية المرشح أو الأصل لا تطابق المفتاح")
    tx = idx.get("transform")
    require(isinstance(tx, dict) and tx.get("fromKey") == target
            and tx.get("fromSha256") == parent_sha, "نسب التحويل لا يطابق الأصل المحدد")
    policy = tx.get("qaDispatch")
    require(isinstance(policy, dict) and policy.get("mode") == "manual-free-only"
            and policy.get("parentSha256") == parent_sha,
            "المرشح لا يحمل طلب الفحص اليدوي المجاني المربوط بهذا الأصل")
    from rename_reciter import entries_sha
    require(tx.get("entriesSha256") == entries_sha(idx.get("entries") or [])
            and tx.get("parentEntriesSha256") == entries_sha(parent.get("entries") or []),
            "بصمات مداخل التحويل لا تطابق محتواه")
    old_ids = [e["ayahId"] for e in parent.get("entries") or []]
    new_ids = [e["ayahId"] for e in idx.get("entries") or []]
    require(len(old_ids) == len(set(old_ids)) and len(new_ids) == len(set(new_ids)),
            "معرفات آيات مكررة")
    require(set(old_ids) <= set(new_ids), "المرشح يفقد مداخل منشورة")
    return idx, parent


def load_bound_candidate(key, sha, parent_sha):
    """قراءة فعلية جديدة، وهوية وبنية ونسب نموذج من الحراس القائمة."""
    import promote as P
    import run as R
    from quran_ctc_model import records_error
    target = parent_key(key)
    client, bucket = P.s3()
    blob = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    parent_blob = client.get_object(Bucket=bucket, Key=target)["Body"].read()
    idx, parent = validate_binding(key, sha, parent_sha, blob, parent_blob)
    frozen, _, _ = P.load_frozen(client, bucket)
    require(frozen.get(target) == parent_sha, "الأصل ليس مجمداً على بصمته المحددة")
    for why in (records_error(idx), P.index_gate(idx, parent=parent, parent_sha=parent_sha),
                P.catalog_gate(idx, P.catalog(client, bucket))):
        require(not why, f"حارس الفهرس: {why}")
    text_path = R.ASSETS / f"text_{idx['riwaya']}.jz"
    require(text_path.is_file(), "النص المرجعي غير موجود في نسخة المستودع")
    canonical = json.loads(gzip.decompress(text_path.read_bytes()))
    require(len(canonical) == 6236, "النص المرجعي ليس 6236 آية")
    fatal, _warn, _info = R.structural(idx, key, allow_unmarked=False, txt_ref=canonical)
    require(not fatal, "الفحص البنيوي قبل الصوت: " + " · ".join(fatal))
    return client, bucket, idx, parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--parent-sha", required=True)
    a = ap.parse_args()
    _client, _bucket, idx, _parent = load_bound_candidate(a.key, a.sha, a.parent_sha)
    print(json.dumps({"key": a.key, "sha256": a.sha, "parentSha256": a.parent_sha,
                      "entries": len(idx["entries"]), "structuralChecked": True,
                      "audioMeasured": False, "productionChanged": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
