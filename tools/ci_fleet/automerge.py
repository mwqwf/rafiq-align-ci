#!/usr/bin/env python3
"""دمجٌ تلقائيٌّ لطلبات فروع claude/ بعد نجاح فحوصها (بإذن المالك 2026-10-17).

المكتبة القياسية فقط. التوكن من AUTOMERGE_TOKEN؛ وإن غاب يخرج بالرمز 0 برسالة.
منطق القرار في الدالة النقية decide() فيُختبر بلا شبكة.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
DEFAULT_REPOS = "all"  # كل مستودعات المالك غير المؤرشفة (أمره 2026-10-17)
OWNER_LOGIN = "mwqwf"
RELEASE_FILE = "store/release-request.json"
BLOCK_LABELS = {"no-automerge", "hold"}
ACTIVE_RUN_STATES = {"queued", "in_progress", "waiting", "pending", "requested"}
OK_CONCLUSIONS = {"success", "skipped", "neutral"}


class AuthError(Exception):
    pass


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def decide(pr, files, check_runs, runs, combined_status, now, min_age_min,
           repo, head_commit_date):
    """تعيد (يُدمج؟، السبب). pr هو الطلب المفرد (فيه mergeable)."""
    head = pr.get("head") or {}
    ref = head.get("ref") or ""
    if not ref.startswith("claude/"):
        return False, "الفرع ليس من claude/"
    head_repo = (head.get("repo") or {}).get("full_name")
    if head_repo != repo:
        return False, "الفرع منسوخ من مستودع آخر"
    if (pr.get("user") or {}).get("login") != OWNER_LOGIN:
        return False, "صاحب الطلب ليس المالك"
    if pr.get("draft"):
        return False, "الطلب مسودة"
    labels = {l.get("name") for l in pr.get("labels") or []}
    if labels & BLOCK_LABELS:
        return False, "عليه وسم إيقاف (%s)" % "، ".join(sorted(labels & BLOCK_LABELS))
    if any(f.get("filename") == RELEASE_FILE for f in files):
        if "release-approved" not in labels:
            return False, "يغيّر %s بلا وسم release-approved" % RELEASE_FILE
    age = (now - parse_time(head_commit_date)).total_seconds() / 60
    if age < min_age_min:
        return False, "إيداع الرأس حديث (%.1f د < %s د)" % (age, min_age_min)
    for r in runs:
        if r.get("status") in ACTIVE_RUN_STATES:
            return False, "تشغيلة جارية: %s" % r.get("name", "؟")
    for c in check_runs:
        if c.get("status") != "completed":
            return False, "فحص غير مكتمل: %s" % c.get("name", "؟")
        if c.get("conclusion") not in OK_CONCLUSIONS:
            return False, "فحص لم ينجح: %s (%s)" % (c.get("name", "؟"), c.get("conclusion"))
    if combined_status and combined_status.get("statuses"):
        if combined_status.get("state") != "success":
            return False, "الحالة المجمعة ليست success (%s)" % combined_status.get("state")
    if pr.get("mergeable") is None:
        return False, "mergeable لم تُحسب بعد؛ تُعاد الدورة القادمة"
    if pr.get("mergeable") is False or pr.get("mergeable_state") == "dirty":
        return False, "تعارض في الدمج"
    return True, "كل الشروط متحققة"


def api(token, method, path, body=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "rafiq-automerge",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise AuthError("401")
        raise


ROLLUP_Q = """query($o:String!,$n:String!,$p:Int!){repository(owner:$o,name:$n){pullRequest(number:$p){
commits(last:1){nodes{commit{oid statusCheckRollup{state contexts(first:100){nodes{
__typename ... on CheckRun{name status conclusion}}}}}}}}}}"""


def rollup_to_checks(data, sha, partial=False):
    """تحوّل جواب GraphQL (statusCheckRollup) إلى قائمة فحوص بصيغة REST.

    بديلُ check-runs حين يرفضه توكن fine-grained في المستودعات الخاصة بـ403.
    الحالات الخارجية (StatusContext) تغطّيها الحالة المجمعة فتُترك هنا.
    """
    nodes = (((data or {}).get("data") or {}).get("repository") or {}).get("pullRequest") or {}
    nodes = ((nodes.get("commits") or {}).get("nodes") or [])
    if not nodes:
        raise ValueError("لا رأس في جواب GraphQL")
    commit = nodes[-1].get("commit") or {}
    if commit.get("oid") != sha:
        raise ValueError("رأس GraphQL لا يطابق رأس الطلب")
    roll = commit.get("statusCheckRollup") or {}
    if partial:
        # بعضُ الفحوص محجوبةٌ عن التوكن (FORBIDDEN): يُحكم بالحالة الإجمالية التي تشملها كلّها
        st = (roll.get("state") or "").upper()
        if st == "SUCCESS":
            return [{"name": "rollup", "status": "completed", "conclusion": "success"}]
        if st in ("PENDING", "EXPECTED"):
            return [{"name": "rollup", "status": "in_progress", "conclusion": None}]
        return [{"name": "rollup", "status": "completed", "conclusion": (st or "unknown").lower()}]
    out = []
    for c in ((roll.get("contexts") or {}).get("nodes") or []):
        if c.get("__typename") != "CheckRun":
            continue
        out.append({"name": c.get("name"), "status": (c.get("status") or "").lower(),
                    "conclusion": (c.get("conclusion") or "").lower() or None})
    return out


def check_runs_for(token, repo, n, sha):
    try:
        return paged(token, "/repos/%s/commits/%s/check-runs" % (repo, sha), "check_runs")
    except urllib.error.HTTPError as e:
        if e.code != 403:
            raise
    o, name = repo.split("/", 1)
    d = api(token, "POST", "/graphql", {"query": ROLLUP_Q, "variables": {"o": o, "n": name, "p": n}})
    errs = (d or {}).get("errors") or []
    if errs and not all(e.get("type") == "FORBIDDEN" for e in errs):
        raise ValueError("GraphQL: %s" % errs[0].get("type", "خطأ"))
    return rollup_to_checks(d, sha, partial=bool(errs))


def paged(token, path, key=None):
    out, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        d = api(token, "GET", "%s%sper_page=100&page=%d" % (path, sep, page))
        items = d.get(key, []) if key else d
        out.extend(items)
        if len(items) < 100:
            return out
        page += 1


def process_repo(token, repo, dry, min_age, now, log):
    meta = api(token, "GET", "/repos/%s" % repo)
    default = meta["default_branch"]
    # سجلّ هذا السير عامّ: لا تُكشف أسماء فحوص المستودع الخاص، يكفي رقم الطلب ونوع السبب
    hide = bool(meta.get("private"))
    prs = paged(token, "/repos/%s/pulls?state=open&base=%s" % (repo, default))
    for p in prs:
        n = p["number"]
        try:
            if not (p["head"]["ref"].startswith("claude/")):
                continue  # لا يهمّنا ولا يُطبع
            sha = p["head"]["sha"]
            files = paged(token, "/repos/%s/pulls/%d/files" % (repo, n))
            checks = check_runs_for(token, repo, n, sha)
            runs = api(token, "GET", "/repos/%s/actions/runs?head_sha=%s&per_page=100" % (repo, sha)).get("workflow_runs", [])
            status = api(token, "GET", "/repos/%s/commits/%s/status" % (repo, sha))
            full = api(token, "GET", "/repos/%s/pulls/%d" % (repo, n))
            cdate = api(token, "GET", "/repos/%s/commits/%s" % (repo, sha))["commit"]["committer"]["date"]
            ok, why = decide(full, files, checks, runs, status, now, min_age, repo, cdate)
            if not ok:
                log("%s#%d: تُخطّي — %s" % (repo, n, why.split(":")[0] if hide else why))
                continue
            if dry:
                log("%s#%d: كان سيُدمج (تجريبي)" % (repo, n))
                continue
            api(token, "PUT", "/repos/%s/pulls/%d/merge" % (repo, n), {
                "merge_method": "squash", "sha": sha,
                "commit_title": "%s (#%d)" % (p["title"], n)})
            log("%s#%d: دُمج" % (repo, n))
        except AuthError:
            raise
        except urllib.error.HTTPError as e:
            # نوعُ النداء المرفوض يدلّ على الإذن الناقص في التوكن (بلا كشف مسارٍ أو اسمِ فحص)
            u = (getattr(e, "url", "") or "").split("?")[0]
            kind = next((k for k in ("check-runs", "actions/runs", "/status", "/files", "/merge", "/commits/", "/pulls/")
                         if k in u), "?")
            # رسالةُ GitHub والإذنُ الذي يطلبه (‏X-Accepted-GitHub-Permissions) يسمّيان النقصَ بلا تخمين
            try:
                msg = (json.loads(e.read().decode() or "{}").get("message") or "")[:120]
            except Exception:  # noqa: BLE001
                msg = ""
            need = (e.headers.get("X-Accepted-GitHub-Permissions") if e.headers else "") or ""
            log("%s#%d: خطأ HTTP %s في %s — تُخطّي%s%s" % (repo, n, e.code, kind.strip("/"),
                " · «%s»" % msg if msg else "", " · الإذن المطلوب: %s" % need if need else ""))
        except Exception as e:  # noqa: BLE001
            log("%s#%d: خطأ %s — تُخطّي" % (repo, n, e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", default=DEFAULT_REPOS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-age-min", type=float, default=5)
    a = ap.parse_args()
    token = os.environ.get("AUTOMERGE_TOKEN")
    if not token:
        print("لا يوجد AUTOMERGE_TOKEN: يلزم المالكَ إضافةُ السرّ AUTOMERGE_TOKEN "
              "في أسرار هذا المستودع؛ لا دمج في هذه الدورة.")
        return 0
    lines = []

    def log(s):
        print(s)
        lines.append(s)

    now = datetime.now(timezone.utc)
    try:
        if a.repos == "all":
            seen = [r for r in paged(token, "/user/repos?affiliation=owner")
                    if not r.get("archived") and not r.get("disabled")]
            repos = [r["full_name"] for r in seen]
            # تشخيص صلاحية التوكن بلا كشف أسماء المستودعات الخاصة في السجل العام
            print("مستودعات يراها التوكن: %d، منها خاصة: %d"
                  % (len(seen), sum(1 for r in seen if r.get("private"))))
        else:
            repos = [r.strip() for r in a.repos.split(",") if r.strip()]
        for repo in repos:
            try:
                process_repo(token, repo, a.dry_run, a.min_age_min, now, log)
            except urllib.error.HTTPError as e:
                log("%s: خطأ HTTP %s — تُخطّي المستودع" % (repo, e.code))
    except AuthError:
        print("فشلت المصادقة (401): التوكن AUTOMERGE_TOKEN غير صالح أو منتهٍ.")
        return 1
    if not lines:
        log("لا طلبات claude/ مفتوحة.")
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write("## الدمج التلقائي\n\n" + "\n".join("- " + l for l in lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
