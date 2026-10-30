#!/usr/bin/env bash
# One-time setup for macOS / Linux:  bash setup.sh
set -e
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
echo
echo "Setup finished. Start the app with:  bash run.sh   (or press F5 in VS Code)"
