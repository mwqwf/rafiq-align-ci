#!/usr/bin/env python3
"""↩️ إعادةُ الحالة إلى الإيداع في المستودع الخاص — برمزٍ دقيق النطاق (Commit statuses: write على QuranRafiq وحده).

⛔ ما يُرسل مقيَّدٌ هنا لا في السير: سياقٌ من قائمةٍ ثابتة، وحالةٌ من أربع، ووصفٌ يُبنى من أعدادٍ فقط (‏≤140 حرفاً)،
   ورابطٌ إمّا صفحةُ التشغيلة العامّة وإمّا رابطٌ موقَّعٌ إلى R2 يُقرأ من ملفٍّ محلّيّ (‏لا يمرّ بالسجلّ).
⛔ ولا يُطبع الرمزُ ولا الرابطُ ولا جسمُ الردّ: المطبوعُ «أُرسلت الحالة» ورمزُ HTTP فقط.
✅ --dry-run: يبني الطلبَ كاملاً ويتحقّق منه ولا يرسله (‏التجربةُ على المستودع العامّ لا رمزَ لها).
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO = "mwqwf/QuranRafiq"
STATES = {"pending", "success", "failure", "error"}
CONTEXT_RE = re.compile(r"(?:ci/app-test|public-ci/[a-z0-9-]{3,40}(?:/[a-z0-9-]{2,24})?)")
SHA_RE = re.compile(r"[0-9a-f]{40}")
RUN_URL_RE = re.compile(r"https://github\.com/mwqwf/rafiq-align-ci/actions/runs/\d+(?:/attempts/\d+)?")
SIGNED_RE = re.compile(r"https://[a-z0-9]{32}\.r2\.cloudflarestorage\.com/mushafak-private/ci/private-ci/\S+")
DESCRIPTIONS = {
    "pending": "قيد التشغيل على العدّاء العام",
    "success": "نجح",
    "failure": "فشل",
    "error": "تعذّر",
}


def build_description(state, counts):
    """وصفٌ من أعدادٍ فقط — لا اسمَ اختبارٍ ولا رسالة."""
    d = DESCRIPTIONS[state]
    if counts:
        t, f, e = (int(counts.get(k, 0)) for k in ("tests", "failures", "errors"))
        d += f" · {t} اختباراً · إخفاق {f} · عطب {e}"
        if counts.get("suspicious"):
            d += " · حُجب الملخّص"
    return d[:140]


def build_payload(state, context, run_url, counts, link=None):
    if state not in STATES:
        raise ValueError("حالةٌ غيرُ مسموحة")
    if not CONTEXT_RE.fullmatch(context or ""):
        raise ValueError("سياقٌ غيرُ مسموح")
    target = link if (link and SIGNED_RE.fullmatch(link)) else run_url
    if not (RUN_URL_RE.fullmatch(target or "") or SIGNED_RE.fullmatch(target or "")):
        raise ValueError("رابطٌ غيرُ مسموح")
    return {"state": state, "context": context, "description": build_description(state, counts),
            "target_url": target}


def send(sha, payload, token, opener=urllib.request.urlopen):
    if not SHA_RE.fullmatch(sha or ""):
        raise ValueError("sha غيرُ صالح")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/statuses/{sha}",
        data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
    try:
        with opener(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def state_from(result, counts):
    """من نتيجة الشوط والأعداد: لا «نجح» بلا اختبارٍ واحدٍ جرى (‏قاعدةُ app-test الأصليّة)."""
    if result == "success":
        if counts is not None and int(counts.get("tests", 0)) < 1:
            return "failure"
        return "success"
    if result == "failure":
        return "failure"
    return "error"


def main(argv=None):
    ap = argparse.ArgumentParser(description="إعادة الحالة إلى المستودع الخاص")
    ap.add_argument("--sha", required=True)
    ap.add_argument("--context", required=True)
    ap.add_argument("--result", required=True, help="success|failure|cancelled|… أو pending")
    ap.add_argument("--run-url", required=True)
    ap.add_argument("--counts", help="ملفّ counts.json")
    ap.add_argument("--link-file", help="ملفّ الرابط الموقَّع (يُقرأ ولا يُطبع)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    counts = None
    if a.counts and os.path.isfile(a.counts):
        with open(a.counts, encoding="utf-8") as f:
            counts = json.load(f)
    state = "pending" if a.result == "pending" else state_from(a.result, counts)
    link = None
    if a.link_file and os.path.isfile(a.link_file):
        with open(a.link_file, encoding="utf-8") as f:
            link = f.read().strip()
    try:
        payload = build_payload(state, a.context, a.run_url, counts, link)
    except ValueError as e:
        print(f"الحالة: ⛔ {e}")
        return 1
    if a.dry_run:
        print(f"الحالة (تجربة — لم تُرسل): {payload['context']} = {payload['state']} · {payload['description']}")
        return 0
    token = os.environ.get("PCI_STATUS_TOKEN", "")
    if not token:
        print("الحالة: ⛔ لا رمزَ لكتابة الحالة")
        return 1
    try:
        code = send(a.sha, payload, token)
    except Exception as e:  # noqa: BLE001
        print(f"الحالة: ⛔ تعذّر الإرسال ({type(e).__name__})")
        return 1
    print(f"الحالة: {'✅' if code == 201 else '⛔'} {payload['context']} = {payload['state']} · HTTP {code}")
    return 0 if code == 201 else 1


if __name__ == "__main__":
    sys.exit(main())
