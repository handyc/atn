# gen-v4 — dimension sweep 2..6D: is the growth->copy flip even/odd parity?
von Neumann lattice d=2..6, mostly K=2 (high-D gets more shards for glider yield, on
enlarged boards to avoid wrap artifacts). Local smoke: 2D growth, 3D copy, 4D growth,
5D copy, 6D COPY -> parity holds through 5D but breaks at 6D (copy dominates as
dimension grows; 2D/4D are low-D growth exceptions). This run quantifies growth% vs
dimension with statistics.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/gen-v4 && sbatch submit.sh' ;
bash pull.sh ; python3 gen_aggregate.py outputs
