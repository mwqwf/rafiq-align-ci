# طلب ثالث: حصة تدريب Vertex AI لبطاقتي L4 (عادية ومتقطّعة) في أربع مناطق أخرى، لأن سعة us-central1 لم تتح
set -uo pipefail
P=black-network-509205-h7
T="$(gcloud auth print-access-token)"; M="$(gcloud config get-value account 2>/dev/null)"
J="Single-digit NVIDIA L4 hours per week to fine-tune a small open-source speech model for a free Quran recitation app; us-central1 has no capacity; spending is capped by a budget."
send() { # $1 id · $2 quotaId · $3 region
  echo "== $3 $2"
  curl -sS -X POST "https://cloudquotas.googleapis.com/v1/projects/$P/locations/global/quotaPreferences?quotaPreferenceId=$1" \
    -H "Authorization: Bearer $T" -H "x-goog-user-project: $P" -H "Content-Type: application/json" \
    -d "{\"service\":\"aiplatform.googleapis.com\",\"quotaId\":\"$2\",\"dimensions\":{\"region\":\"$3\"},\"quotaConfig\":{\"preferredValue\":\"2\"},\"justification\":\"$J\",\"contactEmail\":\"$M\"}" \
    | grep -E '"(preferredValue|grantedValue|reconciling|stateDetail|message)"'
}
for R in us-east4 us-west1 europe-west4 asia-southeast1; do
  send "vx-$R-l4" CustomModelTrainingL4GPUsPerProjectPerRegion "$R"
  send "vx-$R-pl4" CustomModelTrainingPreemptibleL4GPUsPerProjectPerRegion "$R"
done
echo "=== انتهى ==="
