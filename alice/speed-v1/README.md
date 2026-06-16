# speed-v1 — the glider SPEED law via front-velocity theory, at scale
80 tasks (4 fractal families x 20 shards). Per glider: measured speed, drift speed
|F|/(a_self+sum a_p), marginal-stability v*, |F|, lambda. Aggregator fits the best
speed model and classifies pulled (speed~v*) vs pushed (speed<v*). Local smoke
(newton): drift R^2=0.51, |F| 0.14, v* bounds 92%.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/speed-v1 && sbatch submit.sh' ;
bash pull.sh ; python3 speed_aggregate.py outputs
