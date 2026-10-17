@echo off
setlocal
if exist "%~dp0..\..\.venv\Scripts\ruff.exe" (
    set "PATH=%~dp0..\..\.venv\Scripts;%PATH%"
)
ruff check . && ruff format --check .
