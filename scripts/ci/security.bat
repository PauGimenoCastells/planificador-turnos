@echo off
setlocal
if exist "%~dp0..\..\.venv\Scripts\pip-audit.exe" (
    set "PATH=%~dp0..\..\.venv\Scripts;%PATH%"
)
pip-audit
