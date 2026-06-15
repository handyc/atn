#!/usr/bin/env bash
# Operator runs this locally after the job finishes: rsync outputs back.
set -euo pipefail
BUNDLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rsync -av "alice:~/atn-alice/ndca-survey-v1/outputs/" "$BUNDLE/outputs/"
echo
echo "Pulled. Aggregate the library with:"
echo "  python3 $BUNDLE/aggregate.py $BUNDLE/outputs"
