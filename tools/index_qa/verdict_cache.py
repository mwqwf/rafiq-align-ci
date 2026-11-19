"""ذاكرة أحكام محلية بمفتاح الكائن وETag، مشتركة مع promote دون تغيير صيغتها."""
import hashlib
import json


def cached(cdir, key, etag):
    f = cdir / (hashlib.sha256(f"{key}|{etag}".encode()).hexdigest() + ".json")
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:                     # noqa: BLE001
            pass
    return None

def store(cdir, key, etag, data):
    f = cdir / (hashlib.sha256(f"{key}|{etag}".encode()).hexdigest() + ".json")
    try:
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:                         # noqa: BLE001
        pass
