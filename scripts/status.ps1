param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $projectRoot "logs\collector.log"
$backupPath = Join-Path $projectRoot "progress_backup.json"
$lockPath = Join-Path $projectRoot "collector.lock"

Write-Host "== G2B Collector Status =="
Write-Host "Project: $projectRoot"

Write-Host "`n[Task Scheduler]"
Get-ScheduledTask -TaskName "pdeck-g2b-collector" | Select-Object TaskName, State
Get-ScheduledTaskInfo -TaskName "pdeck-g2b-collector" | Select-Object LastRunTime, NextRunTime

Write-Host "`n[Lock File]"
if (Test-Path $lockPath) {
    Get-Content $lockPath
} else {
    Write-Host "No active lock file"
}

Write-Host "`n[Progress Backup]"
if (Test-Path $backupPath) {
    Get-Content $backupPath
} else {
    Write-Host "progress_backup.json not found"
}

Write-Host "`n[Recent Log]"
if (Test-Path $logPath) {
    Get-Content $logPath -Tail 40
} else {
    Write-Host "collector.log not found"
}
