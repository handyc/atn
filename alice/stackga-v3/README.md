# stackga-v3 — evolve stacks that COMPUTE WITH RECURRENCE (feedback-aware)
80 GA islands. The stack is closed into a loop (bottom output -> top input, strength vf
EVOLVABLE) and fitness rewards reservoir/RNN-like dynamics: long fading-MEMORY time +
PERIODICITY under the loop, bounded + active (edge of chaos). Memory measured as a
readout would see it (fixed random spatial projections -> autocorrelation time). Local
smoke (pop12/gen6) already hit memory=28 steps, periodicity 0.88, evolved vf=0.30
(GA keeps the feedback). Verify top genome on held-out seeds before claiming.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/stackga-v3 && sbatch submit.sh' ;
bash pull.sh ; python3 stackga3_aggregate.py outputs
