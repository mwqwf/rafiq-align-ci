#!/usr/bin/env python3
"""فحص المرشح المثبت بأدوات الجودة القائمة، وقراءة أهلية ترقيته دون نشره."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from post_stage_guard import load_bound_candidate, parent_key, require

TINY_SHA256 = "ef01ab441b004f9e6f1ea98d397b43452b3a45efab7c3928ab37af655dde8b52"
CHECKS = ("openers", "census", "rs1", "rs2", "rs3", "rs4", "review")


def provenance():
    """النسب من التشغيل الحقيقي، ولا تنشأ هوية CI للتجارب المحلية."""
    run = os.environ.get("GITHUB_RUN_ID", "")
    commit = os.environ.get("GITHUB_SHA", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    require(os.environ.get("GITHUB_ACTIONS") == "true" and run.isdecimal()
            and re.fullmatch(r"[0-9a-f]{40}", commit)
            and repository == "mwqwf/rafiq-align-ci", "يلزم نسب تشغيل GitHub الفعلي")
    paths = ("tools/index_qa/post_stage_quality.py", "tools/index_qa/post_stage_guard.py",
             "tools/index_qa/ci_run.py", "tools/index_qa/run.py",
             "tools/tasmi_bench/openers_scan.py", "tools/alignment_v3/ctc_opener_probe.py")
    return {"source": "ci", "run_id": run, "commit": commit, "repository": repository,
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "run_url": f"https://github.com/{repository}/actions/runs/{run}",
            "tinyModelSha256": TINY_SHA256,
            "toolSha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}}


def verify_model(model):
    p = Path(model)
    require(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == TINY_SHA256,
            "نموذج المحكم لا يطابق البصمة المعتمدة")
    return p.resolve()


def state_key(key, check):
    flat = key.replace("/", "_")
    if check == "census":
        return f"state-census/{flat}.json"
    require(check in CHECKS[:-1], "فحص غير معروف")
    suffix = ".openers" if check == "openers" else f".audio-{check}"
    return f"state/{flat}{suffix}.json"


def validate_time(rep, check, modified):
    when = rep.get("at") if check == "openers" else rep.get("ts")
    require(isinstance(when, (int, float)) and modified <= when <= time.time() + 5,
            "وقت الشاهد لا يقع بعد رفع المرشح وفي زمن القياس الحقيقي")


def validate_report(rep, key, sha, idx, check):
    require(rep.get("key") == key and rep.get("sha256") == sha,
            "شاهد الجودة لا يطابق كامل بصمة المرشح ومفتاحه")
    require((rep.get("riwaya"), rep.get("reciterId"))
            == (idx["riwaya"], idx["reciterId"]), "هوية شاهد الجودة لا تطابق المرشح")
    if check == "openers":
        import promote as P
        require(rep.get("kind") == "openers" and rep.get("scope") == "full"
                and rep.get("threads") == 4 and P.openers_tool_ok(rep),
                "شاهد المطالع ليس مسحاً كاملاً بالأداة والخيوط المعتمدة")
        rows = rep.get("rows") or []
        require(rows and not rep.get("errors"), "المطالع ناقصة أو تعذر قياسها")
        late = {str(r["surah"]) for r in rows if r.get("verdict") == "late"}
        if late:
            detail = rep.get("lateCtc") or {}
            require(rep.get("lateCtcRule") and P.late_ctc_trusted(rep)
                    and late <= set(detail)
                    and all(isinstance(detail[s], dict) and not detail[s].get("error")
                            and "confirmed" in detail[s] for s in late),
                    "شاهد CTC الثاني للمطالع غير مكتمل أو غير حتمي")
    else:
        salt = "census" if check == "census" else check
        kind = "splice-census" if check == "census" else "audio"
        require(rep.get("source") == "ci" and rep.get("kind") == kind
                and (rep.get("sample") or {}).get("seedSalt") == salt,
                "مصدر الشاهد أو نوعه أو ملحه لا يطابق الفحص المطلوب")


class ReadOnlyClient:
    """منع الكتابة حتى لو تغير سلوك أداة العرض مستقبلاً."""
    def __init__(self, client):
        self.client = client

    def __getattr__(self, name):
        require(name in {"get_object", "head_object", "list_objects_v2", "download_file"},
                f"عملية دلو غير مسموحة في غلاف القراءة: {name}")
        return getattr(self.client, name)

    def get_paginator(self, operation):
        require(operation == "list_objects_v2", "السرد المسموح للكائنات فقط")
        return self.client.get_paginator(operation)


class Publisher(ReadOnlyClient):
    """كاتب شاهد واحد فقط؛ يعيد إثبات الأصل والمرشح قبل حفظ القياس."""
    def __init__(self, client, bucket, key, sha, parent_sha, check, idx, proof, loader=None):
        super().__init__(client)
        self.bucket, self.key, self.sha, self.parent_sha = bucket, key, sha, parent_sha
        self.check, self.idx, self.proof = check, idx, proof
        self.loader = loader or load_bound_candidate
        self.report = None

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        require(Bucket == self.bucket and Key == state_key(self.key, self.check),
                "محاولة كتابة خارج اسم شاهد الجودة المحدد")
        rep = json.loads(Body)
        validate_report(rep, self.key, self.sha, self.idx, self.check)
        _client, bucket, current, _parent = self.loader(self.key, self.sha, self.parent_sha)
        require(bucket == self.bucket and current == self.idx, "تبدل المرشح أثناء القياس")
        modified = self.client.head_object(Bucket=Bucket, Key=self.key)["LastModified"].timestamp()
        validate_time(rep, self.check, modified)
        rep["postStageProvenance"] = self.proof
        body = json.dumps(rep, ensure_ascii=False, indent=1, allow_nan=False).encode()
        result = self.client.put_object(Bucket=Bucket, Key=Key, Body=body, **kwargs)
        require(self.client.get_object(Bucket=Bucket, Key=Key)["Body"].read() == body,
                "قراءة شاهد الجودة بعد كتابته لا تطابق بايتاته")
        self.report = rep
        return result


def audio_check(a, client, bucket, idx, proof):
    import ci_run as C
    import run as R
    import promote as P
    if a.check == "census" and not P.census_surahs(idx):
        print("لا سور دمج أو مصادر بديلة؛ بوابة الإحصاء القائمة لا تطلب شاهداً")
        return 0
    publisher = Publisher(client, bucket, a.key, a.sha, a.parent_sha, a.check, idx, proof)
    argv = ["ci_run.py", "--key", a.key, "--expect-sha", a.sha,
            "--clusters", "20", "--per-cluster", "10", "--source", "ci",
            "--run-id", proof["run_id"]]
    argv += (["--census"] if a.check == "census" else
             ["--seed-salt", a.check, "--out-prefix", "state", "--out-suffix", f".audio-{a.check}"])
    old_argv, old_client, old_rs3 = sys.argv, C._s3_from_env, R.s3
    try:
        sys.argv = argv
        C._s3_from_env = lambda: (publisher, bucket)
        try:
            C.main()
            code = 0
        except SystemExit as exc:
            code = exc.code
    finally:
        sys.argv, C._s3_from_env, R.s3 = old_argv, old_client, old_rs3
    require(publisher.report is not None, "لم ينتج الفحص شاهداً رسمياً")
    require(not (publisher.report.get("sample") or {}).get("errors"), "تعذر قياس نوافذ صوتية")
    if a.check == "census":
        why = P.census_gate(client, bucket, a.key, a.sha, idx)
        require(not why, f"بوابة الإحصاء: {why}")
    return code


def openers_check(a, client, bucket, idx, proof):
    witness = HERE / "state" / (a.key.replace("/", "_") + ".openers.json")
    started = time.monotonic()
    subprocess.run([sys.executable, str(ROOT / "tools/tasmi_bench/openers_scan.py"),
                    "--key", a.key, "--model", a.model, "--threads", "4"], check=True, cwd=ROOT)
    rep = json.loads(witness.read_text())
    if any(r.get("verdict") == "late" for r in rep.get("rows", [])):
        subprocess.run([sys.executable, str(ROOT / "tools/alignment_v3/ctc_opener_probe.py"),
                        "--witness", str(witness), "--riwaya", idx["riwaya"]], check=True, cwd=ROOT)
        rep = json.loads(witness.read_text())
    elapsed = round(time.monotonic() - started)
    tool = "tools/tasmi_bench/openers_scan.py"
    rep["provenance"] = {"source": "ci", "run_id": proof["run_id"], "tool": tool,
                         "tool_sha": proof["toolSha256"][tool], "threads": 4, "elapsedSec": elapsed}
    if elapsed < 60:
        rep["suspiciouslyFast"] = True
    publisher = Publisher(client, bucket, a.key, a.sha, a.parent_sha, a.check, idx, proof)
    publisher.put_object(Bucket=bucket, Key=state_key(a.key, a.check),
                         Body=json.dumps(rep).encode(), ContentType="application/json")
    print(json.dumps({"check": "openers", "sha256": a.sha,
                      "openersVerdict": rep.get("openersVerdict"),
                      "swallowed": rep.get("swallowed"), "lateConfirmed": rep.get("lateConfirmed")},
                     ensure_ascii=False))
    return int(bool(rep.get("swallowed") or rep.get("lateConfirmed")))


def read_reports(client, bucket, key):
    """لا تسقط قراءة متعذرة ولا حكما رافضا قبل حساب التجميع الأصلي."""
    import promote as P
    records = []
    flat = key.replace("/", "_")
    for prefix in P.STATE_PREFIXES:
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix.rstrip("/") + "/" + flat):
            for obj in page.get("Contents", []):
                name = obj["Key"]
                if name.endswith(".json"):
                    rep = json.loads(client.get_object(Bucket=bucket, Key=name)["Body"].read())
                    if rep.get("key") == key:
                        records.append((name, rep))
    return records


def review(a, client, bucket, idx, proof):
    """الحراس الأصلية في عرض جاف محمي، والتجميد لا يتغير على الدلو."""
    import promote as P
    import heard_gate as H
    target = parent_key(a.key)
    modified = client.head_object(Bucket=bucket, Key=a.key)["LastModified"].timestamp()
    checks = ["openers", "rs1", "rs2", "rs3", "rs4"]
    if P.census_surahs(idx):
        checks.append("census")
    for check in checks:
        rep = json.loads(client.get_object(Bucket=bucket, Key=state_key(a.key, check))["Body"].read())
        validate_report(rep, a.key, a.sha, idx, check)
        validate_time(rep, check, modified)
        recorded = rep.get("postStageProvenance") or {}
        require(recorded.get("run_id") == proof["run_id"] and recorded.get("commit") == proof["commit"],
                f"شاهد {check} ليس من دورة الفحص هذه")
        require(not (rep.get("sample") or {}).get("errors"), f"شاهد {check} به نوافذ تعذر قياسها")
    heard = json.loads(client.get_object(Bucket=bucket, Key=H.state_key(a.key))["Body"].read())
    hp = heard.get("provenance") or {}
    validate_time(heard, "heard", modified)
    require(hp.get("run_id") == proof["run_id"] and hp.get("commit") == proof["commit"]
            and heard.get("sha256") == a.sha and heard.get("measurementComplete") is True,
            "شاهد السماع ليس قياساً مكتملاً من دورة الفحص هذه")
    records = read_reports(client, bucket, a.key)
    require(records, "لا أحكام رسمية لعرض الترقية")
    require(not any((r.get("sample") or {}).get("errors") for _, r in records
                    if r.get("sha256") == a.sha), "يوجد حكم صوتي رسمي متعذر القياس على البصمة نفسها")
    old_argv, old_s3, old_frozen, old_reports = sys.argv, P.s3, P.load_frozen, P.REPORTS_CACHE
    def preview_frozen(cl, bkt):
        frozen, body, etag = old_frozen(cl, bkt)
        require(frozen.get(target) == a.parent_sha, "تبدل التجميد أثناء عرض الأهلية")
        return {k: v for k, v in frozen.items() if k != target}, body, etag
    output = io.StringIO()
    try:
        sys.argv = ["promote.py", "--only", a.key]
        P.s3 = lambda: (ReadOnlyClient(client), bucket)
        P.load_frozen = preview_frozen
        P.REPORTS_CACHE = records
        with contextlib.redirect_stdout(output):
            P.main()
    finally:
        sys.argv, P.s3, P.load_frozen, P.REPORTS_CACHE = old_argv, old_s3, old_frozen, old_reports
        print(output.getvalue(), end="")
    require(f"✅ جاهز: {a.key} → {target}" in output.getvalue(), "الحراس الأصلية لم تقبل أهلية الترقية")
    load_bound_candidate(a.key, a.sha, a.parent_sha)
    print(json.dumps({"key": a.key, "sha256": a.sha, "readyForGuardedAdoption": True,
                      "productionChanged": False}, ensure_ascii=False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--parent-sha", required=True)
    ap.add_argument("--check", choices=CHECKS, required=True)
    ap.add_argument("--model", default=os.environ.get("QA_MODEL", ""))
    a = ap.parse_args(argv)
    proof = provenance()
    client, bucket, idx, _parent = load_bound_candidate(a.key, a.sha, a.parent_sha)
    if a.check == "review":
        return review(a, client, bucket, idx, proof)
    a.model = str(verify_model(a.model))
    os.environ["QA_MODEL"] = a.model
    return (openers_check if a.check == "openers" else audio_check)(a, client, bucket, idx, proof)


if __name__ == "__main__":
    raise SystemExit(main())
