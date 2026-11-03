#!/usr/bin/env bash
set -euo pipefail
# A few runner regions hang on Ubuntu mirrors. Verify a fixed publisher archive instead.
python tools/ci_fleet/install_qa_ffmpeg.py
export PATH="$PWD/.qa-tools/bin:$PATH"
ffmpeg -version >/dev/null
ffprobe -version >/dev/null
# QA uses a prebuilt wheel; a source compilation must fail visibly instead of occupying a runner for hours.
python -m pip install --quiet --only-binary=:all: --timeout 60 --retries 2 pywhispercpp==1.5.1 soundfile==0.14.0 numpy==2.4.6 boto3==1.43.123
