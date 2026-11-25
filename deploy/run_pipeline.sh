#!/bin/bash

set -e

cd /home/newera/economic-capital-curve-module

source .venv/bin/activate

export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

python main.py --date "$(date -u +%Y-%m-%d)" --mode scheduled
