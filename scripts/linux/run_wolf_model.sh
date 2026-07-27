#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/c/Users/Rohen/OneDrive/Coding/Two Quant/Models/the-wolf-quant-model"
python scripts/run_production_pipeline.py --mode "${1:-daily}"
