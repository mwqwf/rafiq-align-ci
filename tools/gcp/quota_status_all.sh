# حالة كل طلبات الحصة في المشروع (قراءة فقط)
P=black-network-509205-h7
curl -sS "https://cloudquotas.googleapis.com/v1/projects/$P/locations/global/quotaPreferences" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: $P" \
  | python3 -c "
import json,sys
for q in json.load(sys.stdin).get('quotaPreferences',[]):
    c=q.get('quotaConfig',{})
    st='مقبول' if str(c.get('grantedValue'))==str(c.get('preferredValue')) else ('قيد المراجعة' if q.get('reconciling') else 'مرفوض/جزئي')
    print(q.get('quotaId'), 'المطلوب', c.get('preferredValue'), 'الممنوح', c.get('grantedValue'), '=>', st, c.get('stateDetail',''))
"
