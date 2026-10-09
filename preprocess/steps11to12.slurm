#!/bin/bash
#SBATCH --job-name=azcot-steps11-12
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=02:00:00
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs/steps11to12_%j.log
# Steps 11-12: Level 2 coverages (frostbite, snowfall loads) and their validation. Needs steps 9 and 10 (and step 7's
# t2 histogram, step 2's surface_type). Pass "frostbite" or "snowfall" to build only one family.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-/import/home/jdpaul3/AZCOT/preprocess}"
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
echo "== step 11 level-2 coverages"; $PY step11_level2_coverages.py "$@"
echo "== step 12 validate level 2";  $PY step12_validate_level2.py
