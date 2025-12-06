@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "CLIENT_CONFIG_PATH=%SCRIPT_DIR%client_config.json"
python -m client_agent.agent %*
