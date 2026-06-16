# gen-v2 — direction law on the HEX substrate vs state count K
80 tasks (K in {2,3,4,5,8} x 16 shards). Random low-density hex rules (LUT K^7),
detect gliders, test heading=angle(-F). Complements gen-v1 (square/cube) by sweeping
K on the paper's own hex lattice. Local preview: K2 corr 0.88/2deg, K4 0.68/26deg
(random; fractal-generated K4 is cleaner at 0.95/4deg), K8 -0.47/33deg (copy regime).
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/gen-v2 && sbatch submit.sh' ;
bash pull.sh ; python3 gen_aggregate.py outputs
