#!/usr/bin/env bash
JID=$1; SUB=$2
SSHOPT="-o BatchMode=yes -o ConnectTimeout=15"; BUNDLE=/home/handyc/projects/atn/alice/$SUB
ok(){ local n o; for n in $(seq 12); do o=$(ssh $SSHOPT alice "$1" 2>&1); echo "$o" | grep -q "Permission denied" || { echo "$o"; return 0; }; sleep 3; done; return 1; }
for i in $(seq 160); do
  st=$(ok "sacct -j $JID -n -X -o State 2>/dev/null" | grep -E 'RUNNING|PENDING|COMPLETED|FAILED|CONFIG|COMPLETING')
  act=$(echo "$st" | grep -cE 'RUNNING|PENDING|CONFIG|COMPLETING'); fin=$(echo "$st" | grep -cE 'COMPLETED|FAILED')
  echo "[$SUB] poll $i: active=$act finished=$fin"
  [ "$act" = "0" ] && [ "$fin" -gt 0 ] && break
  sleep 30
done
for n in $(seq 12); do rsync -az -e "ssh $SSHOPT" "alice:atn-alice/$SUB/outputs/" "$BUNDLE/outputs/" 2>/dev/null && break; sleep 3; done
echo "[$SUB] shards/results: $(ls $BUNDLE/outputs/shard_*.tsv $BUNDLE/outputs/result_*.json 2>/dev/null | wc -l)"
python3 "$BUNDLE/aggregate.py" "$BUNDLE/outputs"
echo "[$SUB] DONE_SACCT"
