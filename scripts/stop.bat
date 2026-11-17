@echo off
:: Navigate to project root
cd /d "%~dp0.."

echo ===================================================
echo   TradeDash - Stopping Multi-Broker Platform
echo ===================================================

:: Check if Docker daemon is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Docker Desktop is not running. All services are already stopped.
    exit /b 0
)

docker compose down

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to stop Docker services.
    exit /b %errorlevel%
)

echo.
echo All services have been stopped successfully.

