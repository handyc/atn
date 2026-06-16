# nandga-v2 — gate composition, done honestly (the crux for a CA computer)
64 GA islands search a routing fabric (inputs A,B + constant-TRUE C, detector) for a
universal gate (NAND or NOR). Anti-overfit (v1 was a fake): PHYSICAL anchored threshold
(output = did C reach the detector?, theta = half the C-only reference), 10 seeds/condition,
INPUT-DEPENDENCE requirement, and HELD-OUT accuracy on 14 fresh seeds stored per genome.
Believe only genomes with high HELD-OUT accuracy. NOR is the mechanism-natural gate
(one annihilating input blocks C). Smoke stuck ~40% -> gate composition is genuinely hard.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/nandga-v2 && sbatch submit.sh' ;
bash pull.sh ; python3 ~/projects/atn/nandga2_aggregate.py outputs
