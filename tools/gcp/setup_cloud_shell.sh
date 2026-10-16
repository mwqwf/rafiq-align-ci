# إعداد مشروع Google Cloud لمصحفك — يُلصق كاملاً في Cloud Shell مرة واحدة (2026-10-16)
# ينشئ حساب خدمة بلا مفاتيح، ويربطه بـGitHub Actions عبر OIDC (لا سرّ يُنسخ)،
# ويفعّل الواجهات اللازمة، ويطلب حصة بطاقة L4 واحدة، ويضع تنبيه ميزانية عند 300$.
set -euo pipefail
P="${1:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "$P" ]; then
  # لا مشروع محدد في الصدفة: نأخذ المشروع الوحيد المربوط بالفوترة
  P="$(gcloud projects list --format='value(projectId)' | while read -r x; do
        [ "$(gcloud billing projects describe "$x" --format='value(billingEnabled)' 2>/dev/null)" = "True" ] && echo "$x"; done | head -1)"
fi
[ -n "$P" ] || { echo "لم أجد مشروعاً مفوتراً؛ اكتب: bash setup.sh <PROJECT_ID>"; exit 1; }
gcloud config set project "$P" -q
echo "المشروع: $P"
N="$(gcloud projects describe "$P" --format='value(projectNumber)')"
SA="mushafak-ci@$P.iam.gserviceaccount.com"
gcloud services enable aiplatform.googleapis.com texttospeech.googleapis.com compute.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com storage.googleapis.com cloudquotas.googleapis.com \
  billingbudgets.googleapis.com cloudresourcemanager.googleapis.com
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create mushafak-ci --display-name="Mushafak CI"
for R in roles/aiplatform.user roles/compute.admin roles/storage.admin roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$P" --member="serviceAccount:$SA" --role="$R" --condition=None -q >/dev/null
done
gcloud iam workload-identity-pools describe github --location=global >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create github --location=global --display-name="GitHub"
gcloud iam workload-identity-pools providers describe gh --location=global --workload-identity-pool=github >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc gh --location=global --workload-identity-pool=github \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="(assertion.repository=='mwqwf/rafiq-align-ci' || assertion.repository=='mwqwf/QuranRafiq') && assertion.ref=='refs/heads/main'"
for REPO in mwqwf/rafiq-align-ci mwqwf/QuranRafiq; do
  gcloud iam service-accounts add-iam-policy-binding "$SA" --role=roles/iam.workloadIdentityUser \
    --member="principalSet://iam.googleapis.com/projects/$N/locations/global/workloadIdentityPools/github/attribute.repository/$REPO" -q >/dev/null
done
# حصة بطاقة رسومية واحدة (قد تُقبل فوراً أو بعد مراجعة Google)
gcloud beta quotas preferences create --service=compute.googleapis.com --quota-id=GPUS-ALL-REGIONS-per-project \
  --preferred-value=1 --project="$P" --justification="Training an on-device Quran recitation model" -q 2>/dev/null || \
  echo "تعذّر طلب الحصة آلياً؛ سأطلبها من جهتي"
# تنبيه ميزانية (التنبيه لا يوقف الإنفاق؛ حارس الإطفاء عندنا)
BA="$(gcloud billing projects describe "$P" --format='value(billingAccountName)' | sed 's#billingAccounts/##')"
[ -n "$BA" ] && gcloud billing budgets create --billing-account="$BA" --display-name="mushafak-300" \
  --budget-amount=300USD --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0 -q >/dev/null 2>&1 || true
echo
echo "=== انسخ السطر التالي والصقه في الخيط (ليس سرّاً) ==="
echo "GCP $P $N"
