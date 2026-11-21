#!/usr/bin/env bash
set -e

# Navigate to project root
cd "$(dirname "$0")/.."

echo "==================================================="
echo "  TradeDesk - Starting Multi-Broker Platform"
echo "==================================================="

if [ ! -f ".env" ]; then
    echo "[WARNING] .env file not found in root."
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "Please edit .env with your credentials before continuing."
    else
        echo "[ERROR] No .env or .env.example found. Exiting."
        exit 1
    fi
fi

# Check if Docker daemon is running
if ! docker info > /dev/null 2>&1; then
    echo ""
    echo "[ERROR] Docker daemon is not running!"
    echo "Please start Docker (e.g., 'sudo systemctl start docker') and run this script again."
    echo ""
    exit 1
fi

echo "Syncing environment variables to backend..."
cp -f .env backend/.env

echo "Starting Docker services..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
else
    docker compose up -d
fi

echo ""
echo "==================================================="
echo "  Services are running!"
echo "==================================================="
echo "  - Web Dashboard : http://localhost:3000"
echo "  - Backend Docs  : http://localhost:8000/api/docs"
echo "  - Reverse Proxy : http://localhost"
echo "==================================================="

