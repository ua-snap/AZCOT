#!/bin/bash
#SBATCH --job-name=azcot-v2
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=01:00:00
#SBATCH --array=0-182%25
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_verify/logs/v2_%A_%a.log
# V2: scan all raw SD files for one calendar day per task.
set -euo pipefail
cd /import/home/jdpaul3/AZCOT/verification/scripts
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
$PY v2_sd_day.py "$SLURM_ARRAY_TASK_ID"
