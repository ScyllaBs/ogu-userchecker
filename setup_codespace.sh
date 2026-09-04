#!/usr/bin/env bash
set -e

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Install Linux libraries required by Playwright/Chromium in GitHub Codespaces.
sudo python -m playwright install-deps chromium
python -m playwright install chromium

echo ""
echo "Setup complete. Start the app with:"
echo "  python app.py"
