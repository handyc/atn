# collide-v2 — glider-collision GATE search (heterogeneous CA)
40 tasks over the collide-v1 interactors. Each base -> east|west surgery domains;
measure the truth table over inputs {(0,0),(L,0),(0,R),(L,R)} vs impact parameter
(vertical offset) and seed. OUTPUT = surviving mass. Clean XOR gate = singles survive,
pair annihilates, robustly. Also flags AND/product gates. Finds which bases give a
consistent collision-logic primitive.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/collide-v2 && sbatch submit.sh' ;
bash pull.sh ; python3 collide2_aggregate.py outputs
