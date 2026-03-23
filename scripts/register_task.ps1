param(
    [string]$TaskName = "pdeck-g2b-collector",
    [string]$StartTime = "09:00"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$batPath = Join-Path $projectRoot "run_collector.bat"

if (-not (Test-Path $batPath)) {
    throw "run_collector.bat not found: $batPath"
}

$action = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
# ExecutionTimeLimit 0 = 제한 없음 (기본 3일 제한 등으로 장시간 수집이 끊기지 않게)
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Force | Out-Null

Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object LastRunTime, NextRunTime
