#!/usr/bin/env bash
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rsync -az "alice:~/atn-alice/stackga-v1/outputs/" "$B/outputs/"
echo "aggregate: python3 ~/projects/atn/stackga_aggregate.py $B/outputs"
