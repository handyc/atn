#!/usr/bin/env bash
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rsync -az "alice:~/atn-alice/speed-v1/outputs/" "$B/outputs/"
echo "aggregate: python3 ~/projects/atn/speed_aggregate.py $B/outputs"
