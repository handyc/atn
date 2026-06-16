#!/usr/bin/env bash
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ssh alice "mkdir -p ~/atn-alice/route-v1/outputs"
rsync -az --exclude 'outputs/*' "$B/" "alice:~/atn-alice/route-v1/"
echo "submit: ssh alice 'cd ~/atn-alice/route-v1 && sbatch submit.sh'"
