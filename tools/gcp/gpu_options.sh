# بحث عن طرق البطاقات المتاحة بلا حصة Compute العامة: حصص تدريب Vertex AI الافتراضية (قراءة فقط) + إعادة طلب Compute بقيمة 1
set -uo pipefail
P=black-network-509205-h7
T="$(gcloud auth print-access-token)"
H=(-H "Authorization: Bearer $T" -H "x-goog-user-project: $P")
gcloud services enable aiplatform.googleapis.com cloudquotas.googleapis.com --project "$P" -q
echo "== حصص تدريب Vertex AI بالبطاقات (us-central1 وغيرها)"
tok=""; : > vx.json
while :; do
  curl -sS "https://cloudquotas.googleapis.com/v1/projects/$P/locations/global/services/aiplatform.googleapis.com/quotaInfos?pageSize=500${tok:+&pageToken=$tok}" "${H[@]}" > page.json
  python3 - <<'PY'
import json
d=json.load(open('page.json'))
for q in d.get('quotaInfos',[]):
    qid=q.get('quotaId','')
    if 'custom' in qid.lower() and any(g in qid.lower() for g in ['gpu','l4','t4','a100','tpu']):
        for di in q.get('dimensionsInfos',[]):
            v=di.get('details',{}).get('value','0')
            reg=di.get('dimensions',{}).get('region','*')
            if str(v) not in ('0',''):
                print(qid, reg, v)
print('NEXT',d.get('nextPageToken',''))
PY
  tok=$(python3 -c "import json;print(json.load(open('page.json')).get('nextPageToken',''))")
  [ -n "$tok" ] || break
done 2>&1 | grep -v '^NEXT' | sort | head -40
echo "== إعادة طلب Compute بقيمة 1"
curl -sS -X PATCH "https://cloudquotas.googleapis.com/v1/projects/$P/locations/global/quotaPreferences/gpu-all-regions?updateMask=quotaConfig.preferredValue,justification" "${H[@]}" \
  -H "Content-Type: application/json" \
  -d '{"quotaConfig":{"preferredValue":"1"},"justification":"Single NVIDIA L4 for a few hours per week to fine-tune a small open-source speech model for a free Quran recitation app; spending is capped by budget."}' \
  | grep -E '"(preferredValue|grantedValue|reconciling|stateDetail|message)"'
echo "=== انتهى ==="
