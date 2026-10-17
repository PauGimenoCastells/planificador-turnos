@echo off
setlocal
if exist "%~dp0..\..\.venv\Scripts\pytest.exe" (
    set "PATH=%~dp0..\..\.venv\Scripts;%PATH%"
)
pytest && call "%~dp0e2e.bat"
