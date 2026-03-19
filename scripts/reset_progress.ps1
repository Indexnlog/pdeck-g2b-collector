param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("물품", "공사", "용역", "외자")]
    [string]$Job,

    [Parameter(Mandatory = $true)]
    [int]$Year,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 12)]
    [int]$Month
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".conda\python.exe"

if (-not (Test-Path $pythonPath)) {
    throw "Python runtime not found: $pythonPath"
}

$script = @"
import os
import sys
project_root = r"$projectRoot"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from utils.db import load_progress, save_progress

progress = load_progress()
progress["current_job"] = "$Job"
progress["current_year"] = $Year
progress["current_month"] = $Month
progress["daily_api_calls"] = 0
progress["last_run_date"] = ""
save_progress(progress)
print(progress)
"@

$script | & $pythonPath -
