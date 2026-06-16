# route-v1 — robust glider-routing recipe search (heterogeneous CA)
100 tasks (SLURM array), each evaluates ~14 Newton-glider base rules. Per base, build
direction rules by glider surgery (edit only the 18 single-neighbor entries), tile a
GRADED steering field heading(col): 0->turn_deg over grad_frac of the board, and route
a glider through it. Sweep turn in {60,90,120} deg x grad_frac in {0.85,0.5}; keep the
config with best (low heading-vs-field error, high survival, real net turn). Goal: find
base+field recipes that route a glider cleanly (local single-shot gave loose 37deg;
search already finds 11-15deg with 86-120deg net turns).
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/route-v1 && sbatch submit.sh' ;
bash pull.sh ; python3 route_aggregate.py outputs
