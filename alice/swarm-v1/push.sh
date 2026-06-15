#!/usr/bin/env bash
set -euo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ssh alice "mkdir -p ~/atn-alice/swarm-v1/outputs"
rsync -az --exclude 'outputs/*' "$B/" "alice:~/atn-alice/swarm-v1/"
echo "submit: ssh alice 'cd ~/atn-alice/swarm-v1 && sbatch submit.sh'"
