# swarm-v1 — federated class-4 rule-discovery swarm ("BitTorrent for rulesets")
160 nodes (SLURM array), each owns a shard of fractal-space (distinct seed). Each
discovers class-4 hex rules, publishes them CONTENT-ADDRESSED (sha256(LUT) = piece id,
so peers dedup automatically) with metadata (c4, 3D-class, glider, C6/D6 symmetry,
family, fractal coords). Union of shards = a distributed, queryable rule library.
Operator: bash push.sh ; ssh alice 'cd ~/atn-alice/swarm-v1 && sbatch submit.sh' ;
bash pull.sh ; python3 rulehub.py index outputs ; python3 rulehub.py query outputs --dim 3 --glider
