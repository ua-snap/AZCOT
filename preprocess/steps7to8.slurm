#!/bin/bash
#SBATCH --job-name=azcot-steps7-8
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs/steps7to8_%j.log
# Steps 7-8: t2 / wspd / sd coverages and their validation. Needs step 6 output (and step 2 surface_type).
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-/import/home/jdpaul3/AZCOT/preprocess}"
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
echo "== step 7 extra coverages"; $PY step7_extra_coverages.py
echo "== step 8 validate extra";  $PY step8_validate_extra.py
