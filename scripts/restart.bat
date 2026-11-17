@echo off
:: Navigate to scripts folder
cd /d "%~dp0"

echo ===================================================
echo   TradeDash - Restarting Multi-Broker Platform
echo ===================================================

call "%~dp0stop.bat"
echo.
call "%~dp0start.bat"

