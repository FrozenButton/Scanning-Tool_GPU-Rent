@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "CLIENT_CONFIG_PATH=%SCRIPT_DIR%client_config.json"

REM If no arguments are provided, show a friendly usage hint instead of a raw parser error.
if "%~1"=="" (
    echo Usage: run_client.bat ^<command^> [options]
    echo Commands: login ^| create-key ^| scan ^| poll
    echo Example: run_client.bat login --email user@example.com --password mypass
    echo Example: run_client.bat scan --payload ^"@payload.json^"
    goto :eof
)

python -m client_agent.agent %*
