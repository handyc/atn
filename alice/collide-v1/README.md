# collide-v1 — can surgery re-open glider collisions? (heterogeneous CA)
80 tasks. Each base (verified clean-router gliders from route-v1 + newton gliders) is
surgery'd into two domains: left steers east, right steers west, so two gliders
converge at the domain wall. Run solo-left, solo-right, both; compare combined mass to
superposition. verdict = annihilate (min_ratio<0.5) / product (end_ratio>1.6) /
passthrough. Single-rule collisions are blocked by anisotropy; this asks whether
cross-domain meetings interact — a possible route to glider logic.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/collide-v1 && sbatch submit.sh' ;
bash pull.sh ; python3 collide_aggregate.py outputs
