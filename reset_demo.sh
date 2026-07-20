#!/usr/bin/env bash
# Reset the NexusAI demo to a clean board: fresh dataset, empty ledgers.
# Usage: ./reset_demo.sh   (then restart the backend)
set -euo pipefail
cd "$(dirname "$0")/backend"
rm -f nexus.db nexus_test.db
rm -rf uploads knowledge/ingested
mkdir -p uploads knowledge/ingested
echo "Demo state cleared. Start the backend and the twin regenerates in ~15s:"
echo "  cd backend && .nexus-env/Scripts/python.exe -m uvicorn main:app --port 8000"
