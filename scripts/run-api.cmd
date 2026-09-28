@echo off
cd /d "%~dp0.."
.venv\Scripts\python.exe -m uvicorn src.main:app --port 8000 %*
