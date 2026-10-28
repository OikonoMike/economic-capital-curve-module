#!/bin/bash
cd /home/ubuntu/economic-capital-curve-module
source .venv/bin/activate
python main.py --date $(date +%Y-%m-%d) --mode scheduled
