$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project virtual environment is missing: $Python"
}
Set-Location -LiteralPath $Root
& $Python scripts\run_weekly_production.py
exit $LASTEXITCODE
