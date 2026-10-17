@echo off
setlocal
if exist "%~dp0..\..\.venv\Scripts\python.exe" (
    set "PATH=%~dp0..\..\.venv\Scripts;%PATH%"
)
if "%E2E_DB%"=="" set E2E_DB=test
python manage.py migrate --database "%E2E_DB%"
