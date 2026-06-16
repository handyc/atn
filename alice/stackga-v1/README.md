# stackga-v1 — GA search over WAYS TO STACK glider environments
60 GA islands (distinct seeds), each evolves coupled multi-layer hex-CA "stacking
schemes": L layers, per-layer steered glider directions, an LxL coupling matrix,
per-layer trigger thresholds, a coupling operator (kill/birth/flip/setmax/decay),
coupling probability + period. Fitness rewards EMERGENT interest: bounded + sustained,
stack-level edge-of-chaos (moderate fluctuating change) + spatial structure. Finds
coupling schemes that produce behaviour no single uncoupled layer has.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/stackga-v1 && sbatch submit.sh' ;
bash pull.sh ; python3 stackga_aggregate.py outputs
