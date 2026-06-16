# nandga-v1 — universality by construction: search for a NAND gate
70 GA islands. Layout: inputs A,B + a constant-TRUE source C feed a routing fabric of
steered-glider tiles; gliders annihilate at collisions; a detector reads the output.
Genome = per-tile directions + detector + readout time. Fitness = match to the NAND
truth table (00->1,01->1,10->1,11->0). A 100% NAND => the substrate is computation-
universal. Local smoke found XOR (75% NAND); full islands hunt the constant-routing
that completes NAND.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/nandga-v1 && sbatch submit.sh' ;
bash pull.sh ; python3 ~/projects/atn/nandga_aggregate.py outputs
