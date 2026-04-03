@echo off
cd /d "c:\Users\ekapr\Documents\GitHub\pdeck-g2b-collector"
set PYTHONUTF8=1
if not exist logs mkdir logs
".conda\python.exe" -u collectors\g2b\collect_all.py 2>> logs\collector.log
".conda\python.exe" -u collectors\g2b\fill_gaps.py 2>> logs\collector.log

REM S3 백업 (매일 수집 후 SQLite DB 업로드)
"C:\Program Files\Amazon\AWSCLIV2\aws.exe" s3 cp "D:\pdeck-data\g2b-collector\g2b.db" s3://zigu-data-lake/backup/g2b/g2b.db --no-progress >> logs\collector.log 2>&1

exit /b %errorlevel%
