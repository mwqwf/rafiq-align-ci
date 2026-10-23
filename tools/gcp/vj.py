#!/usr/bin/env python3
# محلّل JSON مهام Vertex لـctl.sh: active | nonterminal | cost <بدء> <سعر> [علاماتالإقلاع] [مهامبلاتشغيل] | last
# علامة الإقلاع: ملفٌّ فارغ gs://…/jobs/<معرّف>.<epoch> تكتبه المهمةُ عند بدء تشغيلها الفعليّ (vertex_train.sh).
import json, sys, time
from datetime import datetime

TERM = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED", "JOB_STATE_PARTIALLY_SUCCEEDED"}
ACT = {"JOB_STATE_PENDING", "JOB_STATE_QUEUED", "JOB_STATE_RUNNING"}
NOT_OK = {"JOB_STATE_CANCELLED", "JOB_STATE_FAILED", "JOB_STATE_EXPIRED"}
MARGIN = 600  # تهيئة العامل قبل أوّل سطر في السكربت (ثوانٍ) تُحسب ضمن المدّة تحفّظاً


def t(x):
    try:
        return datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def jid(j):
    return j["name"].rsplit("/", 1)[-1]


def billable_seconds(jobs, start, ran_names="", skip_ids="", now=None):
    """مجموع ثواني التشغيل الفعليّ. الخطأ في الاتجاه الآمن: المشكوك فيه يُحسب."""
    now = time.time() if now is None else now
    boots = {}
    for n in ran_names.split():
        if "." in n:
            i, e = n.rsplit(".", 1)
            if e.isdigit():
                boots[i] = min(int(e), boots.get(i, 10**12))
    skip = set(skip_ids.split())
    # بدءُ عهد العلامات = أقدم إقلاعٍ مُعلَّم؛ ما أُنشئ بعده بلا علامة وانتهى بغير نجاحٍ لم يُقلع قط
    era = min(boots.values()) if boots else None
    secs = 0.0
    for j in jobs:
        if t(j.get("createTime", "")) < start or not j.get("startTime"):
            continue
        # Vertex يضع startTime لحظةَ القبول ولو بقيت المهمة تنتظر السعة؛ والانتظارُ لا يُحاسَب
        if j.get("state") in ("JOB_STATE_PENDING", "JOB_STATE_QUEUED"):
            continue
        i = jid(j)
        if i in skip:
            continue
        begin = t(j["startTime"])
        if i in boots:
            begin = max(begin, boots[i] - MARGIN)  # من بدء التشغيل الفعليّ لا من القبول
        elif era is not None and j.get("state") in NOT_OK and t(j.get("createTime", "")) >= era - MARGIN:
            continue  # أُنشئت في عهد العلامات ولا علامةَ لها وانتهت بلا نجاح ⇒ لم تجرِ
        end = t(j["endTime"]) if j.get("endTime") else now
        secs += max(0.0, end - begin)
    return secs


def main(argv):
    mode = argv[1]
    try:
        jobs = json.load(sys.stdin)
    except Exception:
        jobs = []
    if mode == "active":
        for j in jobs:
            if j.get("state") in ACT:
                print(jid(j), j["state"].replace("JOB_STATE_", ""))
    elif mode == "nonterminal":
        for j in jobs:
            if j.get("state") not in TERM:
                print(jid(j), j.get("state"))
    elif mode == "cost":
        start, rate = t(argv[2]), float(argv[3])
        secs = billable_seconds(jobs, start, argv[4] if len(argv) > 4 else "", argv[5] if len(argv) > 5 else "")
        print(f"{secs / 3600 * rate:.2f} {len(jobs)}")
    elif mode == "last":
        if not jobs:
            print("NONE NONE 0 0")
        else:
            j = max(jobs, key=lambda x: t(x.get("createTime", "")))
            print(jid(j), j.get("state", "?").replace("JOB_STATE_", ""), int(t(j.get("startTime") or j.get("createTime", ""))), int(t(j.get("endTime", ""))))


if __name__ == "__main__":
    main(sys.argv)
