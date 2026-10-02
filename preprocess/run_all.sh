#!/bin/bash
# Submit the whole AZCOT preprocessing pipeline to SLURM: step 1, then steps 2-5 once step 1 succeeds.
# Run from anywhere:  bash preprocess/run_all.sh
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
mkdir -p /import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs
j1=$(sbatch --parsable step1_reduce_hourly.slurm)
j2=$(sbatch --parsable --dependency=afterok:"$j1" steps2to5.slurm)
echo "submitted step 1 as job $j1 and steps 2-5 as job $j2 (logs in /import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs)"
