# stackga-v2 (DEEPER) — emergent gliders at glider-environment intersections
80 GA islands. Deeper genome: each layer has its own EVOLVABLE fractal rule (cx,cy,span),
plus VERTICAL coupling (adjacent-layer same-cell excitation) on top of the L×L same-cell
coupling. Objective hunts EMERGENT STRUCTURE AT INTERSECTIONS: the field where >=2 layers
overlap must be persistent + bounded + LOCALIZED + coherently TRANSLATING (a glider-like
object the overlap creates). Local smoke (pop12/gen6) already hit fit 0.70: a localized
(occ 0.024) intersection structure moving coherently (motion 0.64, driftR 0.86), L=4,
setmax, vertical coupling on.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/stackga-v2 && sbatch submit.sh' ;
bash pull.sh ; python3 stackga2_aggregate.py outputs
