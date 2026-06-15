#!/usr/bin/env bash
# Operator runs this locally: rsync the bundle up to ALICE.
set -euo pipefail
BUNDLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE="alice:~/atn-alice/c4lib-v1"
ssh alice "mkdir -p ~/atn-alice/c4lib-v1/outputs"
rsync -av --exclude='outputs/shard_*' --exclude='outputs/slurm-*' \
    "$BUNDLE/" "$REMOTE/"
echo
echo "Now submit:"
echo "  ssh alice"
echo "  cd ~/atn-alice/c4lib-v1 && sbatch submit.sh && squeue -u \$USER"
