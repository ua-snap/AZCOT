#!/bin/bash
# Submit the whole AZCOT preprocessing pipeline to SLURM:
#   step 1 (WCT, SL)  -> steps 2-5 (surface_type, coverages, stats, validation)
#   step 6 (2T, WSPD, SD; runs alongside step 1) -> steps 7-8 (coverages, validation; also needs step 2)
#   steps 9 (frostbite) and 10 (snowfall, SNAP ERA5) run alongside -> steps 11-12 (Level 2 coverages, validation;
#   also need steps 2 and 7)
# Run from anywhere:  bash preprocess/run_all.sh
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
mkdir -p /import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs
j1=$(sbatch --parsable step1_reduce_hourly.slurm)
j2=$(sbatch --parsable --dependency=afterok:"$j1" steps2to5.slurm)
j6=$(sbatch --parsable step6_reduce_extra.slurm)
j7=$(sbatch --parsable --dependency=afterok:"$j2":"$j6" steps7to8.slurm)
j9=$(sbatch --parsable step9_reduce_frostbite.slurm)
j10=$(sbatch --parsable step10_reduce_snowfall.slurm)
j11=$(sbatch --parsable --dependency=afterok:"$j7":"$j9":"$j10" steps11to12.slurm)
echo "submitted step 1 ($j1), steps 2-5 ($j2), step 6 ($j6), steps 7-8 ($j7), step 9 ($j9), step 10 ($j10), steps 11-12 ($j11); logs in /import/beegfs/CMIP6/jdpaul3/azcot_preprocess/logs"
