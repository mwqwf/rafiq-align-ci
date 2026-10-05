"""تمييز فحص يدوي فعلي على البصمة نفسها؛ لا يصدر حكم جودة أو ترقية."""
import re

MANUAL_QA_REASON = "مرشح محصور في فحوص يدوية مجانية؛ جميع بوابات الجودة والترقية ما زالت لازمة"


def manual_qa_reason(index, key, parent_sha=None):
    """سبب منع الإطلاق التقليدي لهذا المرشح وحده؛ ليس إعفاءً من حارس جودة.

    سياسة معطوبة تُوقف إطلاق المرشح أيضاً حتى تُصلح، ولا تُسقط فحوصه. العلم
    يخص staging فقط؛ لا يحجز الفهرس المنشور إذا انتقل إليه بعد اكتمال حراسه.
    """
    if not str(key).startswith("timings-staging/") or not isinstance(index, dict):
        return None
    transform = index.get("transform")
    if not isinstance(transform, dict) or "qaDispatch" not in transform:
        return None
    policy = transform["qaDispatch"]
    riwaya, reciter = index.get("riwaya"), index.get("reciterId")
    valid_ids = all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_-]+", x)
                    for x in (riwaya, reciter))
    identity_ok = (valid_ids and re.fullmatch(
        rf"timings-staging/{re.escape(riwaya)}/{re.escape(reciter)}\.[A-Za-z0-9._-]+\.jz", key))
    source_key = transform.get("fromKey")
    source_sha = transform.get("fromSha256")
    parent_ok = (valid_ids and isinstance(source_key, str)
                 and re.fullmatch(
                     rf"(?:timings/{re.escape(riwaya)}/{re.escape(reciter)}|"
                     rf"timings-staging/{re.escape(riwaya)}/{re.escape(reciter)}\.[A-Za-z0-9._-]+)\.jz",
                     source_key)
                 and re.fullmatch(r"[0-9a-f]{64}", str(source_sha or "")))
    if (not isinstance(policy, dict) or policy.get("mode") != "manual-free-only"
            or not identity_ok or not parent_ok or policy.get("parentSha256") != source_sha
            or (parent_sha is not None and parent_sha != source_sha)):
        return "سياسة الفحص اليدوي لا تطابق هوية المرشح وأصله؛ لا إطلاق آلي حتى تُراجع"
    return MANUAL_QA_REASON


def manual_qa_policy(index, parent_key, parent_sha):
    """أنشئ علماً مربوطاً بهوية الأصل، أو ارفضه قبل أي رفع."""
    policy = {"mode": "manual-free-only", "parentSha256": parent_sha}
    transform = dict(index.get("transform") or {})
    transform.update(fromKey=parent_key, fromSha256=parent_sha, qaDispatch=policy)
    proposed = dict(index, transform=transform)
    key = f"timings-staging/{index.get('riwaya')}/{index.get('reciterId')}.manual.jz"
    if manual_qa_reason(proposed, key, parent_sha) != MANUAL_QA_REASON:
        raise ValueError("سياسة الفحص اليدوي تحتاج هوية أصل وبصمة كاملة متطابقتين")
    return policy


def has_current_manual_sample(report, sha):
    sample = report.get('sample') or {}
    return (report.get('sha256') == sha and report.get('source') == 'ci'
            and sample.get('seedSalt') in ('rs1', 'rs2', 'rs3', 'rs4')
            and bool(sample.get('rows')))
