#!/bin/bash
#SBATCH --job-name=azcot-step1
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --time=02:00:00
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs/step1_%j.log
# Step 1 (raw hourly -> per-day min/mean/max). Resumable: re-submit after a failure and finished days are skipped.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-/import/home/jdpaul3/AZCOT/preprocess}"
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
$PY step1_reduce_hourly.py --workers "${SLURM_CPUS_PER_TASK:-24}"
