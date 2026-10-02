#!/bin/bash
# Submit the whole AZCOT preprocessing pipeline to SLURM:
#   step 1 (WCT, SL)  -> steps 2-5 (surface_type, coverages, stats, validation)
#   step 6 (2T, WSPD, SD; runs alongside step 1) -> steps 7-8 (coverages, validation; also needs step 2)
# Run from anywhere:  bash preprocess/run_all.sh
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
mkdir -p /import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs
j1=$(sbatch --parsable step1_reduce_hourly.slurm)
j2=$(sbatch --parsable --dependency=afterok:"$j1" steps2to5.slurm)
j6=$(sbatch --parsable step6_reduce_extra.slurm)
j7=$(sbatch --parsable --dependency=afterok:"$j2":"$j6" steps7to8.slurm)
echo "submitted step 1 ($j1), steps 2-5 ($j2), step 6 ($j6), steps 7-8 ($j7); logs in /import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs"
