@echo off
cd /d "c:\Users\ekapr\Documents\GitHub\pdeck-g2b-collector"
set PYTHONUTF8=1
if not exist logs mkdir logs
".conda\python.exe" -u collectors\g2b\collect_all.py >> logs\collector.log 2>&1
