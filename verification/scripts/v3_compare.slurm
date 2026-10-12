#!/bin/bash
#SBATCH --job-name=azcot-v3
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --array=0-19
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_verify/logs/v3_%A_%a.log
# V3 in 20 chunks (every 20th day); then run v3_merge.py.
set -euo pipefail
cd /import/home/jdpaul3/AZCOT/verification/scripts
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
$PY v3_compare.py --part "$SLURM_ARRAY_TASK_ID" 20
