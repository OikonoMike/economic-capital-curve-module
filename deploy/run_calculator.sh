#!/bin/bash
cd /home/ubuntu/economic-capital-curve-module
source .venv/bin/activate
python run_calculator.py >> /home/ubuntu/calculator.log 2>&1
