#!/usr/bin/env bash
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ssh alice "mkdir -p ~/atn-alice/swarm-v2/outputs"
rsync -az --exclude 'outputs/*' "$B/" "alice:~/atn-alice/swarm-v2/"
echo "submit: ssh alice 'cd ~/atn-alice/swarm-v2 && sbatch submit.sh'"
