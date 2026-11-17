@echo off
setlocal enabledelayedexpansion

:: Navigate to project root
cd /d "%~dp0.."

echo ===================================================
echo   TradeDash - Starting Multi-Broker Platform
echo ===================================================

if not exist ".env" (
    echo [WARNING] .env file not found in root.
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy .env.example .env >nul
        echo Please edit .env with your credentials before continuing.
    ) else (
        echo [ERROR] No .env or .env.example found. Exiting.
        exit /b 1
    )
)

:: Check if Docker daemon is running
docker info >nul 2>&1
if %errorlevel% equ 0 goto docker_ready

echo [INFO] Docker Desktop is not running.
if not exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" goto docker_not_found

echo Launching Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
echo Waiting for Docker engine to initialize (this typically takes 30-45 seconds)...
set retries=0

:wait_docker
ping -n 6 127.0.0.1 >nul
docker info >nul 2>&1
if %errorlevel% equ 0 (
    echo Docker engine is ready!
    goto docker_ready
)

set /a retries+=1
if %retries% geq 20 goto docker_timeout

echo Still waiting for Docker engine... retry %retries% of 20
goto wait_docker

:docker_not_found
echo.
echo [ERROR] Docker Desktop was not found at standard path.
echo Please launch Docker Desktop from your Start menu and wait
echo until the Docker whale icon in the taskbar says "Engine running".
echo Then run this script again.
echo.
exit /b 1

:docker_timeout
echo.
echo [ERROR] Timed out waiting for Docker Desktop to initialize.
echo Please ensure Docker Desktop is open and showing "Engine running", then re-run.
echo.
exit /b 1

:docker_ready

:: Sync root .env to backend\.env so backend container gets latest broker tokens
echo Syncing environment variables to backend...
copy /y ".env" "backend\.env" >nul

echo Starting Docker services...
docker compose up -d

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start Docker services.
    echo Make sure Docker Desktop is running.
    exit /b %errorlevel%
)

echo.
echo ===================================================
echo   Services are running!
echo ===================================================
echo   - Web Dashboard : http://localhost:3000
echo   - Backend Docs  : http://localhost:8000/api/docs
echo   - Reverse Proxy : http://localhost
echo ===================================================
