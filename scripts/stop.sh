#!/usr/bin/env bash
set -e

# Navigate to project root
cd "$(dirname "$0")/.."

echo "==================================================="
echo "  TradeDash - Stopping Multi-Broker Platform"
echo "==================================================="

# Check if Docker daemon is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker daemon is not running. All services are already stopped."
    exit 0
fi

if command -v docker-compose &> /dev/null; then
    docker-compose down
else
    docker compose down
fi

echo ""
echo "All services have been stopped successfully."

