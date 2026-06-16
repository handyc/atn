#!/usr/bin/env bash
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ssh alice "mkdir -p ~/atn-alice/flipflopga-v1/outputs"
rsync -az --exclude 'outputs/*' --exclude '__pycache__' "$B/" "alice:~/atn-alice/flipflopga-v1/"
