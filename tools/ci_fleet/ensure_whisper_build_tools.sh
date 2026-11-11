#!/usr/bin/env bash
set -euo pipefail
# Ubuntu 26.04 يثبّت CMake خارج dpkg؛ غياب حزمته لا يعني غياب الأداة.
# تُستدعى هذه الخطوة عند غياب كاش whisper فقط، ولا تغيّر المحرّك أو حُرّاسه.
usable() {
  command -v "$1" >/dev/null 2>&1 && "$1" --version >/dev/null 2>&1
}

packages=()
if ! usable cmake; then
  packages+=(cmake)
fi
for tool in make gcc g++; do
  if ! usable "$tool"; then
    packages+=(build-essential)
    break
  fi
done

if [ "${#packages[@]}" -eq 0 ]; then
  echo "أدوات بناء whisper جاهزة: cmake make gcc g++؛ لا حاجة إلى apt."
  exit 0
fi

printf 'حزم أدوات البناء الناقصة: %s\n' "${packages[*]}"
net=(-o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20)
timeout 150 sudo apt-get update -qq "${net[@]}"
timeout 300 sudo apt-get install -y -qq --no-install-recommends "${net[@]}" "${packages[@]}"

# نجاح مدير الحزم ليس برهاناً على صلاحية الأداة في PATH (قد يحجبها ثنائي معطوب).
for tool in cmake make gcc g++; do
  if ! usable "$tool"; then
    printf 'تعذّر تشغيل أداة البناء بعد التثبيت: %s\n' "$tool" >&2
    exit 1
  fi
done
echo "أدوات بناء whisper جاهزة بعد التثبيت."
