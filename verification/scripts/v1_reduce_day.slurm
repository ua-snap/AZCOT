#!/bin/bash
#SBATCH --job-name=azcot-v1
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=14G
#SBATCH --time=01:00:00
#SBATCH --array=0-182%40
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_verify/logs/v1_%A_%a.log
# V1: one task per calendar day (0..182). Re-running a task overwrites that day's npz atomically.
set -euo pipefail
cd /import/home/jdpaul3/AZCOT/verification/scripts
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
$PY v1_reduce_day.py "$SLURM_ARRAY_TASK_ID"
