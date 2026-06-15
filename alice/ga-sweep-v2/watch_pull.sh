#!/usr/bin/env bash
# Poll an ALICE array job to completion (retry-tolerant against the flaky login
# pool), then rsync outputs back and aggregate. Usage: watch_pull.sh <JOBID>
set -uo pipefail
JID="${1:?need job id}"
SSHOPT="-o BatchMode=yes -o ConnectTimeout=15"
RBASE="atn-alice/ga-sweep-v2"
BUNDLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# run an ssh command, retrying until we get a NON-denied response; echo stdout
ssh_ok() {
  local n o
  for n in $(seq 10); do
    o=$(ssh $SSHOPT alice "$1" 2>&1)
    if ! grep -q "Permission denied" <<<"$o"; then echo "$o"; return 0; fi
    sleep 2
  done
  return 1
}

echo "watching job $JID ..."
for i in $(seq 80); do
  q=$(ssh_ok "squeue -j $JID -h -o %T") || { echo "poll $i: ssh unreachable, retrying"; sleep 20; continue; }
  active=$(grep -cE 'PENDING|RUNNING|CONFIGURING|COMPLETING|RESIZING' <<<"$q")
  echo "poll $i: $active tasks active"
  [ "$active" = "0" ] && { echo "queue empty -> job finished"; break; }
  sleep 20
done

echo "=== sacct summary ==="
ssh_ok "sacct -j $JID -n -X -o JobID,State | sort | uniq -c -f1 | head" || true

echo "=== rsync pull outputs ==="
for n in $(seq 10); do
  rsync -az -e "ssh $SSHOPT" "alice:$RBASE/outputs/" "$BUNDLE/outputs/" 2>/dev/null && { echo "pull OK"; break; }
  sleep 3
done

echo "=== aggregate ==="
python3 "$BUNDLE/aggregate.py" "$BUNDLE/outputs"
echo "ALICE_WATCH_DONE"
