#!/bin/bash

set -e

cd /home/newera/economic-capital-curve-module

source .venv/bin/activate

python main.py --date "$(date -u +%Y-%m-%d)" --mode scheduled
