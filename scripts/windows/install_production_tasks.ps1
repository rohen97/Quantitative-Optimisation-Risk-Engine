$ErrorActionPreference = "Stop"
$Root = "C:\Users\Rohen\OneDrive\Coding\Two Quant\Models\the-wolf-quant-model"
$Daily = Join-Path $Root "scripts\windows\run_daily_model.ps1"
$Weekly = Join-Path $Root "scripts\windows\run_weekly_model.ps1"
$Monthly = Join-Path $Root "scripts\windows\run_monthly_model.ps1"

schtasks /Create /TN "WolfQuantDailyProduction" /SC DAILY /ST 07:00 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Daily`"" /F
schtasks /Create /TN "WolfQuantWeeklyProduction" /SC WEEKLY /D SAT /ST 09:00 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Weekly`"" /F
schtasks /Create /TN "WolfQuantMonthlyProduction" /SC MONTHLY /D 1 /ST 10:00 /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Monthly`"" /F
