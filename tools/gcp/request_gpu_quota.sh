# طلب حصة بطاقتي L4 لمشروع التدريب عبر Cloud Quotas API (يُشغَّل في Cloud Shell)
set -uo pipefail
P=black-network-509205-h7
T="$(gcloud auth print-access-token)"
M="$(gcloud config get-value account 2>/dev/null)"
req() { # $1 معرّف الطلب · $2 quotaId · $3 الأبعاد JSON
  echo "== $2"
  curl -sS -X POST "https://cloudquotas.googleapis.com/v1/projects/$P/locations/global/quotaPreferences?quotaPreferenceId=$1" \
    -H "Authorization: Bearer $T" -H "x-goog-user-project: $P" -H "Content-Type: application/json" \
    -d "{\"service\":\"compute.googleapis.com\",\"quotaId\":\"$2\",\"dimensions\":$3,\"quotaConfig\":{\"preferredValue\":\"2\"},\"justification\":\"Training an on-device Quran recitation model\",\"contactEmail\":\"$M\"}" \
    | grep -E '"(name|preferredValue|grantedValue|stateDetail|message|status)"' | head -6
}
gcloud services enable cloudquotas.googleapis.com --project "$P" -q
req gpu-all-regions GPUS-ALL-REGIONS-per-project '{}'
req l4-us-central1 NVIDIA-L4-GPUS-per-project-region '{"region":"us-central1"}'
echo "=== انتهى؛ صوّر الشاشة ==="
