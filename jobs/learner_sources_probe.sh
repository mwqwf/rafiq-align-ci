#!/usr/bin/env bash
# 📜 مسبارُ تراخيص مصادر المتعلّمين (خطة الحَكَم 2026-09-25 §٣-د) — **بطاقاتُ HF وحدها، بلا صوت**.
# يقرأ لكل مجموعة: واجهةَ HF (‏الوسوم · cardData.license · gated · آخر تعديل · sha) ونصَّ README
# وملفَّ LICENSE إن وُجد — وكلُّ ملفٍّ نصّيٍّ بسقف 200 ك.ب. ⛔ لا يُنزَّل صوتٌ ولا parquet ولا يُكتب في دلو.
# وحكمُه: «رخصةٌ ثابتة» فقط حين يُطبع نصُّها من البطاقة أو الملفّ؛ والصمتُ يُطبع صمتاً لا يُفسَّر.
set -uo pipefail
python3 - <<'PY'
import json, re, urllib.request, urllib.error

UA = {"User-Agent": "rafiq-align-ci learner_sources_probe (license cards only)"}
CAP = 200_000
BIN = re.compile(r"\.(wav|mp3|flac|ogg|opus|m4a|parquet|arrow|tar|zip|gz|npy|pt|bin|safetensors)$", re.I)


def get(url, cap=CAP):
    req = urllib.request.Request(url, headers=UA)  # السقفُ بـread(cap): لا يُقرأ أكثرُ منه
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(cap).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return 0, repr(e)


# اكتشافُ أسماء IqraEval الحاليّة (‏أسماءُ المجموعات تتبدّل بين الدورات)
st, body = get("https://huggingface.co/api/datasets?author=IqraEval&limit=100")
iqra = [d["id"] for d in json.loads(body)] if st == 200 and body.strip().startswith("[") else []
print(f"== IqraEval: {st} · {len(iqra)} مجموعة: {' · '.join(iqra) or '—'}")

ids = ["RetaSy/quranic_audio_dataset", "IqraEval/QuranMB.v2", "IqraEval/Iqra_Extra_IS26",
       "IqraEval/Iqra_train", "sobolev210/quran-recitation-errors", "obadx/muaalem-annotated-v3"]
ids += [i for i in iqra if i not in ids]

for ds in ids:
    print(f"\n### {ds}")
    st, body = get(f"https://huggingface.co/api/datasets/{ds}")
    if st != 200:
        print(f"  api: {st} ⛔ (لا بطاقة)")
        continue
    try:
        j = json.loads(body)
    except Exception:  # noqa: BLE001
        print("  api: جوابٌ غيرُ JSON (مقطوعٌ بالسقف؟)")
        continue
    card = j.get("cardData") or {}
    tags = [t for t in j.get("tags", []) if t.startswith("license:")]
    sib = [s["rfilename"] for s in j.get("siblings", [])]
    lic_files = [s for s in sib if re.search(r"(^|/)(LICEN[CS]E|COPYING|TERMS)", s, re.I) and not BIN.search(s)]
    print(f"  sha={str(j.get('sha'))[:12]} · آخر تعديل={j.get('lastModified')} · gated={j.get('gated')} · private={j.get('private')}")
    print(f"  cardData.license={card.get('license')!r} · license_name={card.get('license_name')!r} · license_link={card.get('license_link')!r}")
    print(f"  وسوم الرخصة: {tags or 'لا شيء'} · ملفّات: {len(sib)} · ملفّاتُ رخصة: {lic_files or 'لا شيء'}")
    ex = card.get("extra_gated_prompt") or card.get("extra_gated_heading")
    if ex:
        print(f"  شرطُ البوّابة: {str(ex)[:300]!r}")
    st, readme = get(f"https://huggingface.co/datasets/{ds}/resolve/main/README.md")
    hits = [l.strip() for l in readme.splitlines()
            if re.search(r"licen[cs]e|cc[- ]by|creative commons|\bmit\b|apache|non[- ]commercial|terms of use|citation|arxiv|doi", l, re.I)]
    print(f"  README: {st} · {len(readme)} حرفاً · أسطرُ رخصةٍ/استشهاد: {len(hits)}")
    for l in hits[:15]:
        print("    │ " + l[:220])
    for f in lic_files[:3]:
        st, t = get(f"https://huggingface.co/datasets/{ds}/resolve/main/{f}", 20_000)
        print(f"  {f}: {st} · أوّلُه: {' '.join(t.split())[:300]!r}")
PY
