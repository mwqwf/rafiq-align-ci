#!/usr/bin/env python3
"""احرس سجل استئناف الفهرسة من التلف أو الاستبدال غير المقصود.

السجل تراكميّ: الدفعة العادية لا تعيد كتابته، بل تحفظ البايتات السابقة ثم تلحق
قسماً جديداً. هذا الحارس مستقل عن طريقة الدفع، ولذلك يكشف أيضاً خطأ ترميز blob
قبل أن يصبح رأس ``main``.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


DEFAULT_PATH = Path("ops/out/CODEX_INDEXING_RESUME.md")
SECTION = "## متابعة Codex"


def decode_resume(raw: bytes, label: str) -> str:
    if b"\0" in raw:
        raise ValueError(f"{label}: يحتوي NUL؛ ليس Markdown نصياً")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}: ليس UTF-8 صالحاً: {exc}") from exc
    if not text.startswith("# مصحفك: نقطة الاستئناف"):
        raise ValueError(f"{label}: ترويسة سجل الاستئناف مفقودة")
    if not text.endswith("\n"):
        raise ValueError(f"{label}: السطر الأخير بلا newline")
    return text


def require_append_only(candidate: bytes, baseline: bytes) -> dict[str, int]:
    candidate_text = decode_resume(candidate, "candidate")
    baseline_text = decode_resume(baseline, "baseline")
    if not candidate.startswith(baseline):
        common = 0
        for left, right in zip(candidate, baseline):
            if left != right:
                break
            common += 1
        raise ValueError(
            "candidate لا يحفظ baseline بايتياً؛ "
            f"أول اختلاف عند البايت {common} من {len(baseline)}"
        )
    return {
        "baselineBytes": len(baseline),
        "candidateBytes": len(candidate),
        "baselineLines": len(baseline_text.splitlines()),
        "candidateLines": len(candidate_text.splitlines()),
        "baselineSections": baseline_text.count(SECTION),
        "candidateSections": candidate_text.count(SECTION),
    }


def git_blob(ref: str, path: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{ref}:{path.as_posix()}"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--baseline-ref", default="HEAD")
    args = parser.parse_args()
    stats = require_append_only(args.path.read_bytes(), git_blob(args.baseline_ref, args.path))
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
