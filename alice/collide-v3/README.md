# collide-v3 — stable collision-gate truth table (fine impact x timing scan)
42 tasks (1 interactor base each). Dense scan over impact parameter dy (-8..8) x
timing/phase px (-4..4) x 3 seeds. Reports best XOR/AND operating point, its
multi-seed fidelity, and the size of the clean-gate region. collide-v2's gates were
coarse; this asks whether any base has a ROBUST gate region (not just a lucky point).
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/collide-v3 && sbatch submit.sh' ;
bash pull.sh ; python3 collide3_aggregate.py outputs
