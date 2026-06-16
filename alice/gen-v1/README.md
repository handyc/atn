# gen-v1 — universality of the direction law across substrates
99 tasks (9 substrate×K combos × 11 seed-shards). Each generates random low-density
rules for its substrate (square von Neumann / square Moore / 3D cubic von Neumann,
K in 2..5), detects gliders, and tests heading == angle(-F) (F = single-neighbor
activation vector). Maps where the hex-K4 direction law generalises, where it weakens
(high K), and where a copy-regime sign-flip appears (low-K 3D). Self-contained worker
(numpy only). Local check: sq-vn K2 corr 1.00/1deg, sq-Moore K2 0.94/4deg, sq-vn K4
0.71/19deg, cube-vn K3 58deg, cube-vn K2 178deg (inverted).
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/gen-v1 && sbatch submit.sh' ;
bash pull.sh ; python3 gen_aggregate.py outputs
