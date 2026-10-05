#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قياس قارئ لتخزين Actions وعدّائي الفهرسة؛ لا يمنح إذناً مالياً ولا يطلق عملاً."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = "mwqwf/rafiq-align-ci"
ROOT = Path(__file__).resolve().parents[2]
PREFIX = f"repos/{REPO}"
WORKFLOWS = (
    "agent_cmd.yml", "restore.yml", "heard_batch.yml", "audio_qa.yml",
    "openers.yml", "splice_census.yml", "heard_gate.yml", "ctc_splice.yml",
    "realign_surah.yml",
)


class ReadError(RuntimeError):
    """خطأ قراءة بصيغة لا تكشف السجلات أو الاعتمادات."""


def gh_get(endpoint):
    """واجهة GET ثابتة المضيف والمستودع؛ لا تطبع stderr أو الاستجابة الخام."""
    if not (endpoint == PREFIX or endpoint.startswith(PREFIX + "/")) or ".." in endpoint:
        raise ReadError("رُفض مسار خارج المستودع المسموح")
    try:
        result = subprocess.run(
            ["gh", "api", "--hostname", "github.com", "--method", "GET",
             "-H", "Accept: application/vnd.github+json", endpoint],
            capture_output=True, text=True, timeout=90, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ReadError("تعذّر تشغيل قراءة gh أو انتهت مهلتها") from None
    if result.returncode:
        status = re.search(r"\bHTTP\s+(\d{3})\b", result.stderr or "")
        raise ReadError("رُفضت قراءة GitHub" + (f" (HTTP {status[1]})" if status else ""))
    try:
        value = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        raise ReadError("رد GitHub ليس JSON صالحاً") from None
    if not isinstance(value, dict):
        raise ReadError("بنية رد GitHub غير متوقعة")
    return value


def pages(get, endpoint, collection, *, max_pages=200):
    """يحتفظ بالنتائج الجزئية ويمنع إعلان الاكتمال عند فشل صفحة أو تغيّر العدد."""
    items, seen, errors = [], set(), []
    total, fetched_pages = None, 0
    for page in range(1, max_pages + 1):
        separator = "&" if "?" in endpoint else "?"
        try:
            data = get(f"{endpoint}{separator}per_page=100&page={page}")
            batch, current_total = data.get(collection), data.get("total_count")
            if not isinstance(batch, list) or type(current_total) is not int or current_total < 0:
                raise ReadError("قائمة الصفحات أو عددها غير صالح")
            if total is None:
                total = current_total
            elif current_total != total:
                raise ReadError("تغيّر العدد أثناء الجرد؛ لا توجد لقطة مكتملة ثابتة")
            for item in batch:
                identity = item.get("id") if isinstance(item, dict) else None
                if type(identity) is not int or identity in seen:
                    raise ReadError("صفحة فيها معرّف مفقود أو مكرر؛ قد تغيّرت القائمة أثناء الجرد")
                seen.add(identity)
                items.append(item)
            fetched_pages += 1
            if len(items) == total:
                return {"items": items, "pagesRead": fetched_pages, "reportedTotal": total,
                        "readComplete": True, "errors": []}
            if not batch or len(items) > total:
                raise ReadError("انتهت الصفحات قبل مطابقة العدد المعلن")
        except ReadError as ex:
            errors.append(str(ex))
            break
    else:
        errors.append("بلغ الجرد سقف الصفحات؛ لم يكتمل القياس")
    return {"items": items, "pagesRead": fetched_pages, "reportedTotal": total,
            "readComplete": False, "errors": errors}


def artifact_summary(listing):
    """الحجم المقيس ليس حصة الحساب ولا مقدار الفاتورة بوحدة GB-hours."""
    active, expired, invalid = [], 0, 0
    for item in listing["items"]:
        size = item.get("size_in_bytes")
        if type(item.get("expired")) is not bool or type(size) is not int or size < 0:
            invalid += 1
            continue
        if item["expired"]:
            expired += 1
            continue
        active.append({key: item.get(key) for key in (
            "id", "name", "size_in_bytes", "created_at", "updated_at", "expires_at"
        )})
    return {"readComplete": listing["readComplete"] and invalid == 0,
            "pagesRead": listing["pagesRead"], "reportedTotal": listing["reportedTotal"],
            "errors": listing["errors"] + (["آثار ببيانات حجم أو انتهاء غير صالحة"] if invalid else []),
            "observedActiveBytes": sum(item["size_in_bytes"] for item in active),
            "observedActiveCount": len(active), "observedExpiredCount": expired,
            "invalidCount": invalid, "activeArtifacts": active}


def read_section(get, endpoint, keys):
    try:
        raw = get(endpoint)
        if any(key not in raw for key in keys):
            raise ReadError("حقول مطلوبة غائبة من رد GitHub")
        return {"readComplete": True, **{key: raw[key] for key in keys}}
    except ReadError as ex:
        return {"readComplete": False, "error": str(ex)}


def workflow_evidence(get, workflow):
    result = {"path": f".github/workflows/{workflow}"}
    result["metadata"] = read_section(get, f"{PREFIX}/actions/workflows/{workflow}",
                                      ("id", "state", "path"))
    try:
        raw = get(f"{PREFIX}/contents/.github/workflows/{workflow}")
        if raw.get("encoding") != "base64":
            raise ReadError("ترميز ملف workflow غير متوقع")
        source = base64.b64decode(raw["content"]).decode("utf-8")
        # نحتفظ بأسطر الموارد فقط، دون env أو with أو قيم الأسرار.
        resources = []
        for number, line in enumerate(source.splitlines(), 1):
            line = line.split("#", 1)[0].strip()
            if re.search(r"\bruns-on:|\buses:\s*actions/(?:cache|upload-artifact|download-artifact)", line):
                resources.append({"line": number, "text": line})
        result["configuration"] = {"readComplete": True, "sha": raw.get("sha"), "resources": resources}
    except (ReadError, KeyError, ValueError, UnicodeError):
        result["configuration"] = {"readComplete": False, "error": "تعذّرت قراءة إعداد موارد workflow"}
    try:
        recent = get(f"{PREFIX}/actions/workflows/{workflow}/runs?per_page=1").get("workflow_runs")
        if not isinstance(recent, list):
            raise ReadError("قائمة الأشواط غير صالحة")
        if not recent:
            result["latestRun"] = None
            return result
        run = recent[0]
        if type(run.get("id")) is not int:
            raise ReadError("معرّف الشوط غير صالح")
        result["latestRun"] = {key: run.get(key) for key in (
            "id", "head_sha", "created_at", "status", "conclusion", "html_url"
        )}
        jobs = pages(get, f"{PREFIX}/actions/runs/{run['id']}/jobs", "jobs")
        result["jobs"] = {key: value for key, value in jobs.items() if key != "items"}
        result["jobs"]["items"] = [{key: job.get(key) for key in (
            "id", "name", "status", "conclusion", "labels", "runner_name", "runner_group_name"
        )} for job in jobs["items"]]
    except ReadError as ex:
        result["runReadError"] = str(ex)
    return result


def audit(get=gh_get, workflows=WORKFLOWS):
    report = {"schema": 1, "repository": REPO,
              "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "repositoryMetadata": read_section(get, PREFIX, ("full_name", "private", "visibility")),
              "cacheUsage": read_section(get, f"{PREFIX}/actions/cache/usage", (
                  "active_caches_count", "active_caches_size_in_bytes")),
              "artifacts": artifact_summary(pages(get, f"{PREFIX}/actions/artifacts", "artifacts"))}
    for key in ("active_caches_count", "active_caches_size_in_bytes"):
        value = report["cacheUsage"].get(key)
        if report["cacheUsage"]["readComplete"] and (type(value) is not int or value < 0):
            report["cacheUsage"].update(readComplete=False, error="قياس حجم cache غير صالح")
    runners = pages(get, f"{PREFIX}/actions/runners", "runners")
    report["selfHostedRunners"] = {key: value for key, value in runners.items() if key != "items"}
    report["selfHostedRunners"]["countObserved"] = len(runners["items"])
    report["selfHostedRunners"]["note"] = "هذه الواجهة لا تعدّ عدّائي GitHub المستضافين؛ شواهدهم ضمن jobs."
    report["workflows"] = [workflow_evidence(get, workflow) for workflow in workflows]
    report["costDecision"] = {
        "freeExecutionVerified": False,
        "accountArtifactQuotaKnown": False,
        "accountSharedStorageUsageKnown": False,
        "cacheBillingLimitKnown": False,
        "r2QuotaKnown": False,
        "reason": "حجم مستودع واحد لا يثبت الحصة المجانية المتبقية للتخزين المشترك على الحساب. "
                  "لا تقيس هذه الأداة حصة R2 أو فوترة الحساب، ولا تجيز إطلاق محاذاة جديدة.",
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="ops/out/free-compute-audit.json", help="تقرير JSON داخل ops/out فقط")
    parser.add_argument("--workflow", action="append", choices=WORKFLOWS,
                        help="workflows المراد قياسها؛ الافتراض جميع سيور الفهرسة المدرجة")
    args = parser.parse_args()
    if os.environ.get("GITHUB_REPOSITORY", REPO) != REPO:
        parser.error("الأداة مقيدة بالمستودع mwqwf/rafiq-align-ci")
    output = ROOT / args.out
    if output.is_symlink() or output.resolve().parent != (ROOT / "ops/out").resolve() or output.suffix != ".json":
        parser.error("المخرج يجب أن يكون ملف JSON داخل ops/out فقط")
    report = audit(workflows=args.workflow or WORKFLOWS)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"كُتب تقرير القراءة: {output.relative_to(ROOT)}")
    print("لم تثبت المجانية: حصة تخزين الحساب المتبقية غير معروفة؛ راجع التقرير.")
    return 0 if all(report[key]["readComplete"] for key in (
        "repositoryMetadata", "cacheUsage", "artifacts")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
