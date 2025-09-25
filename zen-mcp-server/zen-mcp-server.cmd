@echo off
cd /d "%~dp0"
if exist ".zen_venv\Scripts\python.exe" (
    .zen_venv\Scripts\python.exe server.py %*
) else (
    python server.py %*
)
