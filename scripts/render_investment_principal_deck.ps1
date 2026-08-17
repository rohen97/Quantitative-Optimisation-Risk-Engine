param([switch]$SkipBuild, [string]$PdfPath)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Output = Join-Path $RepoRoot (
    'reports\presentations\wolf_investment_principal'
)
$Deck = Join-Path $Output 'wolf_quant_model_ic_briefing.pptx'
$UseDatedDefault = [string]::IsNullOrWhiteSpace($PdfPath)
if ($UseDatedDefault) {
    $Pdf = Join-Path $Output (
        'wolf_quant_model_ic_briefing_' +
        [DateTime]::UtcNow.ToString('yyyy-MM-dd') + '.pdf'
    )
}
elseif ([IO.Path]::IsPathRooted($PdfPath)) {
    $Pdf = $PdfPath
}
else {
    $Pdf = Join-Path $RepoRoot $PdfPath
}

function Install-RenderedPdf {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    if (-not (Test-Path -LiteralPath $Destination)) {
        [IO.File]::Move($Source, $Destination)
        return
    }
    $Backup = (
        $Destination + '.' + [Guid]::NewGuid().ToString('N') + '.bak'
    )
    try {
        [IO.File]::Replace($Source, $Destination, $Backup, $true)
    }
    finally {
        if (Test-Path -LiteralPath $Backup) {
            [IO.File]::Delete($Backup)
        }
    }
}

if (-not $SkipBuild) {
    & $Python (
        Join-Path $PSScriptRoot 'build_investment_principal_deck.py'
    )
    if ($LASTEXITCODE -ne 0) {
        throw 'PowerPoint build failed.'
    }
}

$PdfDirectory = Split-Path -Parent $Pdf
[IO.Directory]::CreateDirectory($PdfDirectory) | Out-Null
$TempPdf = Join-Path $PdfDirectory (
    '.' + [IO.Path]::GetFileNameWithoutExtension($Pdf) + '.' +
    [Guid]::NewGuid().ToString('N') + '.pdf'
)

$PowerPoint = New-Object -ComObject PowerPoint.Application
$Presentation = $null
try {
    $Presentation = $PowerPoint.Presentations.Open($Deck, 0, 0, 0)
    # Render completely before replacing any published artifact.
    $Presentation.SaveCopyAs($TempPdf, 32, 0)
    $Presentation.Close()
    [Runtime.InteropServices.Marshal]::ReleaseComObject(
        $Presentation
    ) | Out-Null
    $Presentation = $null
    try {
        Install-RenderedPdf -Source $TempPdf -Destination $Pdf
    }
    catch [IO.IOException] {
        if (-not $UseDatedDefault) {
            throw
        }
        $FallbackPdf = Join-Path $PdfDirectory (
            [IO.Path]::GetFileNameWithoutExtension($Pdf) + '_' +
            [DateTime]::UtcNow.ToString('yyyy-MM-dd') + '.pdf'
        )
        try {
            Install-RenderedPdf -Source $TempPdf -Destination $FallbackPdf
        }
        catch [IO.IOException] {
            $FallbackPdf = Join-Path $PdfDirectory (
                [IO.Path]::GetFileNameWithoutExtension($Pdf) + '.' +
                [DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss') + '.pdf'
            )
            Install-RenderedPdf -Source $TempPdf -Destination $FallbackPdf
        }
        $Pdf = $FallbackPdf
    }
}
finally {
    if ($null -ne $Presentation) {
        try { $Presentation.Close() } catch { }
        [Runtime.InteropServices.Marshal]::ReleaseComObject(
            $Presentation
        ) | Out-Null
    }
    $PowerPoint.Quit()
    [Runtime.InteropServices.Marshal]::ReleaseComObject(
        $PowerPoint
    ) | Out-Null
    if (Test-Path -LiteralPath $TempPdf) {
        Remove-Item -LiteralPath $TempPdf -Force
    }
}

& $Python (
    Join-Path $PSScriptRoot 'build_investment_principal_deck.py'
) --register-rendered-pdf --rendered-pdf $Pdf

if ($LASTEXITCODE -ne 0) {
    throw 'Rendered PDF manifest registration failed.'
}

Write-Output ('PowerPoint: ' + $Deck)
Write-Output ('PDF: ' + $Pdf)
