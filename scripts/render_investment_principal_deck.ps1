param([switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Output = Join-Path $RepoRoot (
    'reports\presentations\wolf_investment_principal'
)
$Deck = Join-Path $Output 'wolf_quant_model_ic_briefing.pptx'
$Pdf = Join-Path $Output 'wolf_quant_model_ic_briefing.pdf'

if (-not $SkipBuild) {
    & $Python (
        Join-Path $PSScriptRoot 'build_investment_principal_deck.py'
    )
    if ($LASTEXITCODE -ne 0) {
        throw 'PowerPoint build failed.'
    }
}

$PowerPoint = New-Object -ComObject PowerPoint.Application
try {
    $Presentation = $PowerPoint.Presentations.Open($Deck, 0, 0, 0)

    $Presentation.SaveAs($Pdf, 32)
    $Presentation.Close()
}
finally {
    $PowerPoint.Quit()
    [Runtime.InteropServices.Marshal]::ReleaseComObject(
        $PowerPoint
    ) | Out-Null
}

& $Python (
    Join-Path $PSScriptRoot 'build_investment_principal_deck.py'
) --register-rendered-pdf

if ($LASTEXITCODE -ne 0) {
    throw 'Rendered PDF manifest registration failed.'
}

Write-Output ('PowerPoint: ' + $Deck)
Write-Output ('PDF: ' + $Pdf)
