#!/bin/bash
# gen.sh <L|A> سور بفواصل → rewindow
python3 - "$1" "$2" <<'P'
import json,sys
r=json.load(open(f"/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad/rng_{sys.argv[1]}.json"))
print(",".join(r[s] for s in sys.argv[2].split(",")))
P
