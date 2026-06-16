#!/usr/bin/env bash
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rsync -az "alice:~/atn-alice/stackga-v3/outputs/" "$B/outputs/"
echo "aggregate: python3 ~/projects/atn/stackga3_aggregate.py $B/outputs"
