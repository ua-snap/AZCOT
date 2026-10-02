#!/bin/bash
#SBATCH --job-name=azcot-step6
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=18
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs/step6_%j.log
# Step 6 (raw hourly 2T, WSPD, SD -> per-day min/mean/max + monthly histograms + freeze-thaw). One task per
# (variable, month); finished months are skipped on re-submit.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-/import/home/jdpaul3/AZCOT/preprocess}"
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
$PY step6_reduce_extra.py --workers "${SLURM_CPUS_PER_TASK:-18}"
