@echo off
REM Daily Pinterest Board Auto-Remake
REM Pulls latest code, then runs the VPS remake pipeline

cd /d "%~dp0.."

REM Pull latest code from GitHub
echo [%date% %time%] Git pull...
git pull origin main

REM Ensure logs dir exists
if not exist "logs" mkdir logs

REM Run the remake pipeline
echo [%date% %time%] Starting remake pipeline...
python pipeline\vps_remake.py >> logs\daily-remake.log 2>&1

echo [%date% %time%] === Remake completed === >> logs\daily-remake.log
