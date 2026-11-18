#!/bin/bash

set -e

cd /home/ubuntu/economic-capital-curve-module

source .venv/bin/activate

python main.py --date "$(date -u +%Y-%m-%d)" --mode scheduled
