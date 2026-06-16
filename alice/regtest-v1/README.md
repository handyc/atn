# regtest-v1 — thorough test of the CA memory register
Top-5 evolved flip-flop genomes (from flipflopga-v1) x N(8,16,32) bits x hold(250,600)
steps, 12 random words each. Builds N latch cells on one shared board; write/hold/read;
reports bit-fidelity and whole-word-perfect rate at checkpoints. Maps register CAPACITY
(cross-talk at large N?) and RETENTION (still 100% at long holds?).
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/regtest-v1 && sbatch submit.sh' ;
bash pull.sh ; python3 regtest_aggregate.py outputs
