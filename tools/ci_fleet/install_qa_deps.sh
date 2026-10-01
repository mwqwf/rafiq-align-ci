#!/usr/bin/env bash
set -euo pipefail
# The standard Ubuntu runner already has ffmpeg; do not wait on apt mirrors unnecessarily.
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  timeout 180s sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 update -qq
  timeout 180s sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 install -y -qq ffmpeg
fi
ffmpeg -version >/dev/null
ffprobe -version >/dev/null
# QA uses a prebuilt wheel; a source compilation must fail visibly instead of occupying a runner for hours.
python -m pip install --quiet --only-binary=:all: --timeout 60 --retries 2 pywhispercpp soundfile numpy boto3
