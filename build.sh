#!/bin/bash
set -e

echo "Downloading dependencies..."
virtualenv -p python3 venv
source venv/bin/activate
pip3 install -r requirements.txt
deactivate
echo "Done."
