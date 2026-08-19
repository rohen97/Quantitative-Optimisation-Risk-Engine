param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath $Root).Path
$Daily = Join-Path $Root "scripts\windows\run_daily_model.ps1"
$Weekly = Join-Path $Root "scripts\windows\run_weekly_model.ps1"
$Monthly = Join-Path $Root "scripts\windows\run_monthly_model.ps1"

foreach ($Script in @($Daily, $Weekly, $Monthly)) {
    if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) {
        throw "Missing production task runner: $Script"
    }
}

function Register-WolfTask {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string[]]$Schedule,
        [Parameter(Mandatory)] [string]$Script
    )

    $Action = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Script`""
    & schtasks.exe /Create /TN $Name @Schedule /TR $Action /F | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to register scheduled task $Name (exit $LASTEXITCODE)."
    }
}

Register-WolfTask -Name "WolfQuantDailyProduction" -Schedule @("/SC", "DAILY", "/ST", "07:00") -Script $Daily
Register-WolfTask -Name "WolfQuantWeeklyProduction" -Schedule @("/SC", "WEEKLY", "/D", "SAT", "/ST", "09:00") -Script $Weekly
Register-WolfTask -Name "WolfQuantMonthlyProduction" -Schedule @("/SC", "MONTHLY", "/MO", "FIRST", "/D", "SUN", "/ST", "10:00") -Script $Monthly
