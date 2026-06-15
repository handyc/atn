#!/usr/bin/env bash
#SBATCH --job-name=c4lib-v2
#SBATCH --partition=cpu-short
#SBATCH --time=01:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --array=0-255
#SBATCH --output=outputs/slurm-%A_%a.out
#SBATCH --error=outputs/slurm-%A_%a.err
set -euo pipefail

# ALICE Python + numpy via the standard module stack; self-adapting:
# pinned version -> generic -> user-pip fallback (proven on prior cell8 runs).
# If `module avail Python` shows different versions, edit the pinned lines.
module load Python/3.11.5-GCCcore-13.2.0 2>/dev/null   || module load Python 2>/dev/null || true
module load SciPy-bundle/2023.11-gfbf-2023b 2>/dev/null || module load SciPy-bundle 2>/dev/null || true
python3 -c 'import numpy' 2>/dev/null || pip install --user --quiet --disable-pip-version-check numpy

# SLURM runs scripts from a dir the job can't write to; go back to the bundle.
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")}"
python3 run_task.py "$SLURM_ARRAY_TASK_ID"
