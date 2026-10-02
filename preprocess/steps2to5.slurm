#!/bin/bash
#SBATCH --job-name=azcot-steps2-5
#SBATCH --partition=t1small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs/steps2to5_%j.log
# Steps 2-5: surface_type flag, climatology coverages, stats coverages, validation. Needs step 1 output.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-/import/home/jdpaul3/AZCOT/preprocess}"
PY=${PY:-/import/home/jdpaul3/micromamba/envs/azcot-preprocess/bin/python}
echo "== step 2 surface_type";  $PY step2_surface_type.py
echo "== step 3 climatology";   $PY step3_climatology.py
echo "== step 4 stats";         $PY step4_stats.py --workers "${SLURM_CPUS_PER_TASK:-12}"
echo "== step 5 validate";      $PY step5_validate.py
