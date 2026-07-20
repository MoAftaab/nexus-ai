@echo off
REM Reset the NexusAI demo to a clean board: fresh dataset, empty ledgers.
cd /d "%~dp0backend"
del /q nexus.db nexus_test.db 2>nul
rmdir /s /q uploads 2>nul
rmdir /s /q knowledge\ingested 2>nul
mkdir uploads 2>nul
mkdir knowledge\ingested 2>nul
echo Demo state cleared. Start the backend and the twin regenerates in ~15s:
echo   cd backend ^&^& .nexus-env\Scripts\python.exe -m uvicorn main:app --port 8000
