#!/bin/bash
#SBATCH --job-name=azcot-step9
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=24
#SBATCH --mem=96G
#SBATCH --time=03:00:00
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs/step9_%j.log
# Step 9 (raw hourly 2T + WS10 -> frostbite-time histograms per calendar day). One task per day; finished days are
# skipped on re-submit.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-/import/home/jdpaul3/AZCOT/preprocess}"
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
$PY step9_reduce_frostbite.py --workers "${SLURM_CPUS_PER_TASK:-24}" "$@"
