@echo off
setlocal
if exist "%~dp0..\..\.venv\Scripts\pytest.exe" (
    set "PATH=%~dp0..\..\.venv\Scripts;%PATH%"
)
set APP_ENV=test
set E2E_DB=test
call "%~dp0provision-e2e.bat" && pytest tests/e2e
