#!/usr/bin/env bash
#SBATCH --job-name=ga-sweep-v1
#SBATCH --partition=cpu-short
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --array=0-71
#SBATCH --output=outputs/slurm-%A_%a.out
#SBATCH --error=outputs/slurm-%A_%a.err
set -euo pipefail
module load Python/3.11.5-GCCcore-13.2.0 2>/dev/null   || module load Python 2>/dev/null || true
module load SciPy-bundle/2023.11-gfbf-2023b 2>/dev/null || module load SciPy-bundle 2>/dev/null || true
python3 -c 'import numpy' 2>/dev/null || pip install --user --quiet --disable-pip-version-check numpy
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")}"
python3 run_task.py "$SLURM_ARRAY_TASK_ID"
