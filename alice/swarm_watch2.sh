#!/usr/bin/env bash
JID=$1; SSHOPT="-o BatchMode=yes -o ConnectTimeout=15"
B=/home/handyc/projects/atn/alice/swarm-v2; R=/home/handyc/projects/atn/rulehub.py
ok(){ local n o; for n in $(seq 12); do o=$(ssh $SSHOPT alice "$1" 2>&1); echo "$o" | grep -q "Permission denied" || { echo "$o"; return 0; }; sleep 3; done; return 1; }
for i in $(seq 320); do
  st=$(ok "sacct -j $JID -n -X -o State 2>/dev/null" | grep -E 'RUNNING|PENDING|COMPLETED|FAILED|CONFIG|COMPLETING')
  act=$(echo "$st" | grep -cE 'RUNNING|PENDING|CONFIG|COMPLETING'); fin=$(echo "$st" | grep -cE 'COMPLETED|FAILED')
  echo "[swarm2] poll $i: active=$act finished=$fin"
  [ "$act" = "0" ] && [ "$fin" -gt 0 ] && break
  sleep 30
done
echo "[swarm2] pulling MANIFESTS ONLY (pieces stay distributed on ALICE)..."
for n in $(seq 12); do rsync -az -e "ssh $SSHOPT" --include='manifest_*.jsonl' --exclude='*' \
    "alice:~/atn-alice/swarm-v2/outputs/" "$B/outputs/" 2>/dev/null && break; sleep 4; done
echo "[swarm2] manifests pulled: $(ls $B/outputs/manifest_*.jsonl 2>/dev/null | wc -l)"
echo "=== INDEX ==="; python3 $R index $B/outputs
echo "=== QUERY: 3D-class4 gliders ==="; python3 $R query $B/outputs --dim 3 --glider -n 6
echo "=== QUERY: D6-symmetric + glider + 3D (premium) ==="; python3 $R query $B/outputs --dim 3 --glider --sym D6 -n 8
echo "SWARM2_DONE"
