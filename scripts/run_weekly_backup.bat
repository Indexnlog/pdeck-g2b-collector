@echo off
cd /d "c:\Users\ekapr\Documents\GitHub\pdeck-g2b-collector"
set PYTHONUTF8=1
if not exist logs mkdir logs
python -u scripts\weekly_parquet_backup.py >> logs\weekly_backup.log 2>&1
exit /b %errorlevel%
