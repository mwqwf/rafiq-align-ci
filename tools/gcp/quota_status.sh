# قراءة حالة طلبات حصة GPU (قراءة فقط، يُشغَّل في Cloud Shell)
set -uo pipefail
P=black-network-509205-h7
T="$(gcloud auth print-access-token)"
for id in gpu-all-regions l4-us-central1; do
  echo "== $id"
  curl -sS "https://cloudquotas.googleapis.com/v1/projects/$P/locations/global/quotaPreferences/$id" \
    -H "Authorization: Bearer $T" -H "x-goog-user-project: $P" \
    | grep -E '"(preferredValue|grantedValue|reconciling|stateDetail|message)"'
done
echo "== الحصة الفعلية"
gcloud compute project-info describe --project "$P" --format="value(quotas)" | tr ';' '\n' | grep -i -E "GPUS_ALL_REGIONS|NVIDIA_L4" 
echo "=== انتهى ==="
