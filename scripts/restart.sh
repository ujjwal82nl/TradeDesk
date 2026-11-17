#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(dirname "$0")"

echo "==================================================="
echo "  TradeDash - Restarting Multi-Broker Platform"
echo "==================================================="

"$SCRIPT_DIR/stop.sh"
echo ""
"$SCRIPT_DIR/start.sh"

