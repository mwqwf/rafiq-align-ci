# طلب ثانٍ: بطاقة Compute واحدة + حصة تدريب Vertex AI لبطاقتي L4 في us-central1
set -uo pipefail
P=black-network-509205-h7
T="$(gcloud auth print-access-token)"; M="$(gcloud config get-value account 2>/dev/null)"
J="Single-digit NVIDIA L4 hours per week to fine-tune a small open-source speech model for a free Quran recitation app; spending is capped by a budget."
send() { # $1 id · $2 service · $3 quotaId · $4 dims · $5 value
  echo "== $3"
  curl -sS -X POST "https://cloudquotas.googleapis.com/v1/projects/$P/locations/global/quotaPreferences?quotaPreferenceId=$1" \
    -H "Authorization: Bearer $T" -H "x-goog-user-project: $P" -H "Content-Type: application/json" \
    -d "{\"service\":\"$2\",\"quotaId\":\"$3\",\"dimensions\":$4,\"quotaConfig\":{\"preferredValue\":\"$5\"},\"justification\":\"$J\",\"contactEmail\":\"$M\"}" \
    | grep -E '"(preferredValue|grantedValue|reconciling|stateDetail|message)"'
}
send gpu-all-1 compute.googleapis.com GPUS-ALL-REGIONS-per-project '{}' 1
for q in CustomModelTrainingL4GPUsPerProjectPerRegion CustomModelTrainingPreemptibleL4GPUsPerProjectPerRegion; do
  send "vx-$(echo $q | tr 'A-Z' 'a-z' | cut -c1-40)" aiplatform.googleapis.com "$q" '{"region":"us-central1"}' 2
done
echo "=== انتهى ==="
