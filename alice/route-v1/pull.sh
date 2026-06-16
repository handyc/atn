#!/usr/bin/env bash
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rsync -az "alice:~/atn-alice/route-v1/outputs/" "$B/outputs/"
echo "aggregate: python3 ~/projects/atn/route_aggregate.py $B/outputs"
