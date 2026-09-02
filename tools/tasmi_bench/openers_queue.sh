#!/usr/bin/env bash
# طابور فحص المطالع بترتيب bd. لا يعيد ما كُتب شاهدُه.
cd "$(dirname "$0")/../.." || exit 1
for key in "$@"; do
  st="tools/index_qa/state/$(echo "$key" | tr '/' '_').openers.json"
  if [ -f "$st" ]; then echo "== تخطٍّ (شاهدٌ موجود): $key"; continue; fi
  echo "== $key"
  PYTHONIOENCODING=utf-8 python tools/tasmi_bench/openers_scan.py --key "$key" --threads 4 2>&1 \
    | grep -E "^  س|^[a-z0-9_]+: \{" 
done
