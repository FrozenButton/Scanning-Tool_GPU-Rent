@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "RENTAL_CONFIG_PATH=%SCRIPT_DIR%rental_config.json"
set "PROVIDER_CONFIG_PATH=%SCRIPT_DIR%provider_config.json"

start "GPU Rental Backend" cmd /k python -m rental_service.server
start "GPU Worker" cmd /k python -m provider_service.service
