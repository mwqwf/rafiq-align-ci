# -*- coding: utf-8 -*-
"""جدول القراء المُمرأين — من سجل النتائج المقيس لا من طوابع السجل.

    python3 mirror_table.py [عدد]     # على الخادم
"""
import json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = os.environ.get("FOLLOW_RESULTS", "/root/follower_results.jsonl")
n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
rows = [json.loads(l) for l in open(P, encoding="utf-8") if l.strip()] if os.path.exists(P) else []
if n:
    rows = rows[:n]
print("| # | القارئ | الرواية | 114/114؟ | sha MATCH؟ | زمن المرآة | نُزّل | بصمة عيّنة | الساعة |")
print("|---:|---|---|---|---|---:|---:|---|---|")
for i, r in enumerate(rows, 1):
    ok = "✅ 114/114" if r.get("complete") else f"⛔ {r.get('files','?')}/114"
    m = r.get("shaMatch")
    sha = ("✅ MATCH" if m == "MATCH" else f"⚠️ {m} ({r.get('shaOk','?')}/114)") if m else "—"
    s = r.get("seconds")
    print(f"| {i} | `{r['reciter']}` | {r['riwaya']} | {ok} | {sha} | "
          f"{f'{s//60}د {s%60}ث' if s is not None else '—'} | {r.get('downloaded','—')} | "
          f"`{(r.get('sampleSha') or '—')[:16]}…` | {time.strftime('%H:%M', time.localtime(r['ts']))} |")
if not rows:
    print("\n(لا قارئ مُرئي بعد — الأسطول لم يرفع فهرساً جديداً.)")
