# flipflopga-v1 — evolve a flippable CA flip-flop (1 bit of rewritable memory)
60 GA islands. Genome = two layers' fractal rules + SET/RESET pulse size & duration;
two mutually-annihilating layers. Fitness rewards the full cycle SET->A, RESET->B,
SET->A-again with each state dominant + persistent + bounded. Local smoke found a clean
flippable flip-flop on a HELD-OUT seed: set (99,0), reset (6,183), set (154,0). This is
designed digital memory (vs the failed analog reservoir).
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/flipflopga-v1 && sbatch submit.sh' ;
bash pull.sh ; python3 ~/projects/atn/flipflopga_aggregate.py outputs
