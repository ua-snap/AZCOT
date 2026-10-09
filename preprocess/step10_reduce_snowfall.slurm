#!/bin/bash
#SBATCH --job-name=azcot-step10
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=110G
#SBATCH --time=03:00:00
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs/step10_%j.log
# Step 10 (SNAP ERA5 hourly snowfall -> per-winter 24-hour and storm-total loads). One task per winter (~6-8 GB each);
# finished winters are skipped on re-submit. Reading is I/O-bound on the AKCASC file system.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-/import/home/jdpaul3/AZCOT/preprocess}"
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
$PY step10_reduce_snowfall.py --workers "${SLURM_CPUS_PER_TASK:-12}" "$@"
