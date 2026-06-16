# gen-v3 — growth->copy crossover of the direction law vs DIMENSION and K
81 tasks: von Neumann lattice d=2,3,4, K=2..6. Maps where heading=angle(-F) (growth)
gives way to the copy regime (motion toward F). Local preview is striking and
NON-MONOTONIC in dimension: vn2 K2 growth (0deg), vn3 K2 pure copy (179deg), vn4 K2
growth again (2deg) -> possible even/odd dimension-parity flip of the +180 sign.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/gen-v3 && sbatch submit.sh' ;
bash pull.sh ; python3 gen_aggregate.py outputs
