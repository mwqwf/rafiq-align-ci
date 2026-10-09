#!/bin/bash
# rd.sh <اسم ملف الإخراج بلا مسار> — يقرأ مخرجاً من origin/main
cd /tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad/fixD/clone; git fetch -q origin; git show origin/main:ops/out/$1
