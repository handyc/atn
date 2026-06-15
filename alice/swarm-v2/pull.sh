#!/usr/bin/env bash
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rsync -az "alice:~/atn-alice/swarm-v2/outputs/" "$B/outputs/"
echo "index: python3 ~/projects/atn/rulehub.py index $B/outputs"
