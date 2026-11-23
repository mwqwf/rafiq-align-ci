#!/usr/bin/env bash
# تشغيل أعمال فهرسة خفيفة على الصندوق موازاةً لعدّائي GitHub العامّين.
# لا يرقّي ولا يلمس المنشور الحيّ. المحاذاة الثقيلة تبقى على ubuntu-latest.
set -euo pipefail
MIN_MEM_KB=1572864   # 1.5 GiB
LOCK=/tmp/mushafak-box-light.lock
NICE="${NICE_LEVEL:-15}"

avail=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
echo "MemAvailable=${avail} kB  (الحد ${MIN_MEM_KB})"
if [[ -z "$avail" || "$avail" -lt "$MIN_MEM_KB" ]]; then
  echo "رفض: الذاكرة المتاحة دون 1.5 جيغا — لا شغل ثقيل على الصندوق." >&2
  exit 2
fi
if [[ -e "$LOCK" ]] && kill -0 "$(cat "$LOCK")" 2>/dev/null; then
  echo "رفض: شغل خفيف/ثقيل واحد فقط في كل مرة (pid $(cat "$LOCK"))." >&2
  exit 3
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

if [[ $# -lt 1 ]]; then
  echo "الاستعمال: $0 <أمر…>" >&2
  exit 1
fi
echo "nice -n $NICE: $*"
exec nice -n "$NICE" -- "$@"
