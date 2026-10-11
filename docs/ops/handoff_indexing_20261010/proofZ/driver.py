#!/usr/bin/env python3
# سائق الحملة: يطلق heard_pub.yml على الفهارس بترتيب الانحراف دون إغراق الطابور. قابل للاستئناف.
import json, os, subprocess, sys, time, datetime
REPO = "/home/user/rafiq-align-ci"
CLONE = "/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/proofZ/clone"
SP = "/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/proofZ"
ST = SP + "/driver_state.json"
MAX_MINE = int(os.environ.get("MAX_MINE", "2"))
MAX_OTHERS = int(os.environ.get("MAX_OTHERS", "12"))
SHARDS = os.environ.get("SHARDS", "4")
def sh(cmd, **k):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, **k)
def gh(path):
    r = sh(["gh", "api", path]); 
    try: return json.loads(r.stdout)
    except Exception: return None
def load():
    try: return json.load(open(ST))
    except Exception: return {"queue": [], "dispatched": {}, "done": []}
def save(s): json.dump(s, open(ST, "w"), ensure_ascii=False, indent=1)
def counts():
    t = {}
    for st in ("in_progress", "queued", "pending"):
        d = gh(f"repos/mwqwf/rafiq-align-ci/actions/runs?status={st}&per_page=100")
        t[st] = d["workflow_runs"] if d else None
    return t
def main():
    s = load()
    if not s["queue"] and not s["dispatched"] and not s["done"]:
        sys.exit("لا طابور")
    while True:
        c = counts()
        if any(v is None for v in c.values()):
            time.sleep(60); continue
        allr = [r for v in c.values() for r in v]
        mine = [r for r in allr if r["path"].endswith("heard_pub.yml") and any(k in r["display_title"] for k in list(s["dispatched"]))]
        others = len([r for r in c["queued"] + c["pending"] if r not in mine])
        titles = {r["display_title"] for r in mine}
        # حدّث المنتهي
        for k, v in list(s["dispatched"].items()):
            running = any(k in t for t in titles)
            age = time.time() - v["ts"]
            if not running and age > 600:
                s["done"].append(k); del s["dispatched"][k]
        if len(mine) < MAX_MINE and len(allr) < 20 and s["queue"] and all(time.time() - v["ts"] > 240 for v in s["dispatched"].values()):
            key = s["queue"].pop(0)
            f = f"ops/commands/20261009_{datetime.datetime.utcnow().strftime('%H%M%S')}_proofZ_hp.json"
            def g(*a):
                return subprocess.run(["git", *a], capture_output=True, text=True, cwd=CLONE)
            g("fetch", "-q", "origin", "main"); g("reset", "-q", "--hard", "origin/main")
            os.makedirs(CLONE + "/ops/commands", exist_ok=True)
            json.dump({"action": "dispatch", "workflow": "heard_pub.yml",
                       "inputs": {"key": key, "shards": SHARDS, "surahs": "", "force": "false"}}, open(f"{CLONE}/{f}", "w"))
            g("add", f)
            g("commit", "-q", "-m", f"ops: أمر proofZ لقياس خرائط السماع {key}\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01SQoynCHdh8JeGQW5FiQC2r", "--", f)
            ok = False
            for i in range(6):
                if g("push", "-q", "origin", "HEAD:main").returncode == 0:
                    ok = True; break
                g("fetch", "-q", "origin", "main"); g("rebase", "-q", "origin/main") if False else g("merge", "-q", "--no-edit", "origin/main")
            if not ok:
                s["queue"].insert(0, key); print("تعذّر الدفع", key, flush=True); save(s); time.sleep(60); continue
            s["dispatched"][key] = {"ts": time.time(), "cmd": f}
            print(time.strftime("%H:%M:%S"), "أُطلق", key, "others", others, "mine", len(mine), "left", len(s["queue"]), flush=True)
        save(s)
        if not s["queue"] and not s["dispatched"] and not mine:
            print("انتهى الطابور", flush=True); return
        time.sleep(90)
main()
