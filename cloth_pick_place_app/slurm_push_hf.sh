#!/bin/bash
# Batch job: push the finished dataset to Hugging Face from an HPC login/compute
# node (no GPU needed). The interactive data-collection server itself is NOT
# run on Slurm -- it needs a browser + the robot/camera rig -- but this
# upload step is.
#
# Submit with:  sbatch slurm_push_hf.sh
#SBATCH --job-name=push_cloth_pickplace_hf
#SBATCH --time=01:00:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=2
#SBATCH --output=logs/push_hf_%j.log

set -euo pipefail
cd "$(dirname "$0")"

module load python 2>/dev/null || true
python -m pip install --user -r requirements.txt
python push_to_hf.py "$@"
