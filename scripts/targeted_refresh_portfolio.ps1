[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$WorkbookPath,
    [string]$StatusPath = "",
    [string]$LogPath = "",
    [ValidateRange(1, 30)]
    [int]$DeadlineMinutes = 12,
    [ValidateRange(1, 10)]
    [int]$PollSeconds = 2,
    [ValidateRange(2, 6)]
    [int]$StablePolls = 3,
    [switch]$UseCachedProviderEvidence
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'Run this script with Windows PowerShell 5.1 (powershell.exe), not PowerShell Core.'
}
if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne [Threading.ApartmentState]::STA) {
    throw 'Excel COM requires STA. Run: powershell.exe -NoProfile -STA -File scripts\targeted_refresh_portfolio.ps1 ...'
}

$resolvedWorkbook = [IO.Path]::GetFullPath($WorkbookPath)
if (-not (Test-Path -LiteralPath $resolvedWorkbook -PathType Leaf)) {
    throw "Workbook not found: $resolvedWorkbook"
}
if ([IO.Path]::GetExtension($resolvedWorkbook) -ine '.xlsx') {
    throw "Expected an .xlsx workbook: $resolvedWorkbook"
}
$workbookStem = [IO.Path]::GetFileNameWithoutExtension($resolvedWorkbook)
if ($workbookStem -notmatch '(?i)_REPAIRED(?:$|[_-])') {
    throw "Refusing to open a workbook that is not explicitly named as a repaired copy: $resolvedWorkbook"
}

$workbookDirectory = [IO.Path]::GetDirectoryName($resolvedWorkbook)
if ([string]::IsNullOrWhiteSpace($StatusPath)) {
    $StatusPath = [IO.Path]::Combine($workbookDirectory, $workbookStem + '.targeted-refresh.status.txt')
}
else {
    $StatusPath = [IO.Path]::GetFullPath($StatusPath)
}
if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = [IO.Path]::Combine($workbookDirectory, $workbookStem + '.targeted-refresh.log')
}
else {
    $LogPath = [IO.Path]::GetFullPath($LogPath)
}
foreach ($outputPath in @($StatusPath, $LogPath)) {
    $outputDirectory = [IO.Path]::GetDirectoryName($outputPath)
    if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
        throw "Output directory does not exist: $outputDirectory"
    }
}

$script:RunDeadline = (Get-Date).AddMinutes($DeadlineMinutes)
$script:DefaultStablePolls = $StablePolls
$script:PollMilliseconds = $PollSeconds * 1000
$script:TransientPattern = '(?i)Requesting Data|Retrieving Data|#BUSY!|#GETTING_DATA|#CONNECT!|#WAIT!'
$script:Completed = $false

function Write-Status([string]$value) {
    [IO.File]::WriteAllText($StatusPath, $value, [Text.UTF8Encoding]::new($false))
}

function Write-Log([string]$message) {
    $line = '{0:yyyy-MM-dd HH:mm:ss} {1}' -f (Get-Date), $message
    [IO.File]::AppendAllText($LogPath, $line + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

function Release-Com($object) {
    if ($null -ne $object -and [Runtime.InteropServices.Marshal]::IsComObject($object)) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($object)
    }
}

function Set-Formula($cell, [string]$formula2, [string]$formula) {
    if (-not [string]::IsNullOrWhiteSpace($formula2)) {
        try {
            $cell.Formula2 = $formula2
            return
        }
        catch {
            if ([string]::IsNullOrWhiteSpace($formula)) {
                throw
            }
        }
    }
    if ([string]::IsNullOrWhiteSpace($formula)) {
        throw 'No restorable Excel formula was supplied'
    }
    $cell.Formula = $formula
}

function Assert-BeforeDeadline([string]$context) {
    if ((Get-Date) -ge $script:RunDeadline) {
        throw "Hard refresh deadline exceeded during: $context"
    }
}

function Test-IsNumeric($value) {
    return (
        $value -is [byte] -or
        $value -is [int16] -or
        $value -is [int32] -or
        $value -is [int64] -or
        $value -is [single] -or
        $value -is [double] -or
        $value -is [decimal]
    )
}

function Get-RangeState($range) {
    $rows = $null
    $columns = $null
    $cells = $null
    $parts = New-Object Collections.Generic.List[string]
    $total = 0
    $formulaCount = 0
    $numericCount = 0
    $noDataCount = 0
    $blankCount = 0
    $transientCount = 0
    $errorCount = 0
    $otherTextCount = 0
    try {
        $rows = $range.Rows
        $columns = $range.Columns
        $cells = $range.Cells
        $rowCount = [int]$rows.Count
        $columnCount = [int]$columns.Count
        for ($rowIndex = 1; $rowIndex -le $rowCount; $rowIndex++) {
            for ($columnIndex = 1; $columnIndex -le $columnCount; $columnIndex++) {
                $cell = $null
                try {
                    $cell = $cells.Item($rowIndex, $columnIndex)
                    $total++
                    if ([bool]$cell.HasFormula) {
                        $formulaCount++
                    }
                    $text = [string]$cell.Text
                    $value = $cell.Value2
                    $valueText = [string]::Format(
                        [Globalization.CultureInfo]::InvariantCulture,
                        '{0}',
                        $value
                    )
                    $parts.Add($text + [char]31 + $valueText)

                    if ($text -match $script:TransientPattern) {
                        $transientCount++
                    }
                    elseif ($text -match '(?i)^#N/A N/A(?:$|\s)') {
                        # Bloomberg uses this text value for a terminal no-observation result.
                        $noDataCount++
                    }
                    elseif ($text -match '(?i)^#(?:VALUE!|REF!|DIV/0!|NAME\?|NUM!|NULL!|SPILL!|CALC!|FIELD!|BLOCKED!|N/A$)') {
                        $errorCount++
                    }
                    elseif (Test-IsNumeric $value) {
                        $numericCount++
                    }
                    elseif ([string]::IsNullOrWhiteSpace($text)) {
                        $blankCount++
                    }
                    elseif ($text.StartsWith('#')) {
                        $errorCount++
                    }
                    else {
                        $otherTextCount++
                    }
                }
                finally {
                    Release-Com $cell
                }
            }
        }
    }
    finally {
        Release-Com $cells
        Release-Com $columns
        Release-Com $rows
    }

    $payload = $parts -join [char]30
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
        $hash = [BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }

    return [pscustomobject]@{
        Hash = $hash
        Total = $total
        Formula = $formulaCount
        Numeric = $numericCount
        NoData = $noDataCount
        Blank = $blankCount
        Transient = $transientCount
        Error = $errorCount
        OtherText = $otherTextCount
    }
}

function Test-RangeStateValid($state, [ValidateSet('NumericOnly', 'NumericOrNoData')][string]$mode) {
    if ($state.Formula -ne $state.Total) {
        return $false
    }
    if ($state.Transient -ne 0 -or $state.Error -ne 0 -or $state.Blank -ne 0 -or $state.OtherText -ne 0) {
        return $false
    }
    if ($mode -eq 'NumericOnly') {
        return ($state.Numeric -eq $state.Total)
    }
    return (($state.Numeric + $state.NoData) -eq $state.Total)
}

function Invoke-TargetedRangeCalculation(
    $workbook,
    $excel,
    [string]$sheetName,
    [string]$address,
    [ValidateSet('NumericOnly', 'NumericOrNoData')]
    [string]$mode,
    [int]$minimumWaitSeconds = 0,
    [int]$requiredStablePolls = 0
) {
    if ($requiredStablePolls -le 0) {
        $requiredStablePolls = $script:DefaultStablePolls
    }
    Assert-BeforeDeadline "$sheetName!$address calculation"
    $worksheet = $null
    $range = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $range = $worksheet.Range($address)
        Write-Log "Targeted calculation begin: $sheetName!$address mode=$mode"
        try {
            $range.Dirty()
        }
        catch {
            Write-Log "Range.Dirty was unavailable for $sheetName!$address; Range.Calculate will still be used: $($_.Exception.Message)"
        }
        [void]$range.Calculate()

        $started = Get-Date
        $lastHash = ''
        $stableCount = 0
        $pollCount = 0
        $lastState = $null
        while ((Get-Date) -lt $script:RunDeadline) {
            Start-Sleep -Milliseconds $script:PollMilliseconds
            $pollCount++
            $lastState = Get-RangeState $range
            $elapsedSeconds = ((Get-Date) - $started).TotalSeconds
            $calculationDone = ([int]$excel.CalculationState -eq 0)
            $ready = [bool]$excel.Ready
            $valid = Test-RangeStateValid $lastState $mode

            if (
                $valid -and
                $ready -and
                $elapsedSeconds -ge $minimumWaitSeconds -and
                $lastState.Hash -eq $lastHash
            ) {
                $stableCount++
            }
            else {
                $stableCount = 0
            }
            $lastHash = $lastState.Hash

            if (($pollCount % [Math]::Max(1, [int](15 / $PollSeconds))) -eq 0) {
                Write-Log (
                    "Poll $sheetName!$address stable=$stableCount/$requiredStablePolls " +
                    "state=$($excel.CalculationState) ready=$ready numeric=$($lastState.Numeric) " +
                    "noData=$($lastState.NoData) blank=$($lastState.Blank) transient=$($lastState.Transient) " +
                    "errors=$($lastState.Error) other=$($lastState.OtherText)"
                )
            }
            if ($stableCount -ge $requiredStablePolls) {
                Write-Log (
                    "Targeted calculation stable: $sheetName!$address polls=$pollCount " +
                    "numeric=$($lastState.Numeric) noData=$($lastState.NoData) hash=$($lastState.Hash)"
                )
                return $lastState
            }
        }
        $description = if ($null -eq $lastState) {
            'no range state was captured'
        }
        else {
            "numeric=$($lastState.Numeric) noData=$($lastState.NoData) blank=$($lastState.Blank) " +
            "transient=$($lastState.Transient) errors=$($lastState.Error) other=$($lastState.OtherText)"
        }
        throw "Targeted calculation did not stabilize before the hard deadline: $sheetName!$address ($description)"
    }
    finally {
        Release-Com $range
        Release-Com $worksheet
    }
}

function Assert-CachedRangeState(
    $workbook,
    [string]$sheetName,
    [string]$address,
    [ValidateSet('NumericOnly', 'NumericOrNoData')]
    [string]$mode
) {
    $worksheet = $null
    $range = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $range = $worksheet.Range($address)
        $state = Get-RangeState $range
        if (-not (Test-RangeStateValid $state $mode)) {
            throw (
                "Cached provider evidence is invalid: $sheetName!$address " +
                "numeric=$($state.Numeric) noData=$($state.NoData) blank=$($state.Blank) " +
                "transient=$($state.Transient) errors=$($state.Error) other=$($state.OtherText)"
            )
        }
        Write-Log (
            "Validated cached provider evidence: $sheetName!$address " +
            "numeric=$($state.Numeric) noData=$($state.NoData) hash=$($state.Hash)"
        )
        return $state
    }
    finally {
        Release-Com $range
        Release-Com $worksheet
    }
}

function Assert-NoBloombergFormula($range, [string]$label) {
    # Excel's Find can search a dynamic-array anchor's surrounding spill/cache
    # even when the Range itself is one cell. Inspect a single cell directly so
    # a neighbouring BDP formula cannot create a false positive for the master.
    if ([double]$range.CountLarge -eq 1) {
        $formula2 = ''
        try { $formula2 = [string]$range.Formula2 } catch {}
        $formula = [string]$range.Formula
        foreach ($candidate in @($formula2, $formula)) {
            if ($candidate -match '(?i)\b(?:BDP|BDH|BDS|BQL)\(') {
                throw "Downstream range unexpectedly contains a Bloomberg call: $label"
            }
        }
        return
    }
    foreach ($needle in @('BDP(', 'BDH(', 'BDS(', 'BQL(')) {
        $found = $null
        try {
            # xlFormulas=-4123, xlPart=2, xlByRows=1, xlNext=1
            $found = $range.Find($needle, [Type]::Missing, -4123, 2, 1, 1, $false, $false, $false)
            if ($null -ne $found) {
                throw "Downstream range unexpectedly contains a Bloomberg call ($needle): $label"
            }
        }
        finally {
            Release-Com $found
        }
    }
}

function Reset-DerivedSpillArray(
    $workbook,
    [string]$sheetName,
    [string]$masterAddress,
    [string]$fullArrayAddress
) {
    Assert-BeforeDeadline "$sheetName!$fullArrayAddress spill-array reset"
    $worksheet = $null
    $master = $null
    $fullArray = $null
    $cells = $null
    $fullRows = $null
    $fullColumns = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $master = $worksheet.Range($masterAddress)
        $fullArray = $worksheet.Range($fullArrayAddress)
        if (-not [bool]$master.HasFormula) {
            throw "Spill master is not a formula: $sheetName!$masterAddress"
        }
        Assert-NoBloombergFormula $master "$sheetName!$masterAddress"

        $masterFormula2 = ''
        try { $masterFormula2 = [string]$master.Formula2 } catch {}
        $masterFormula = [string]$master.Formula
        if ([string]::IsNullOrWhiteSpace($masterFormula2) -and [string]::IsNullOrWhiteSpace($masterFormula)) {
            throw "Spill master formula could not be snapshotted: $sheetName!$masterAddress"
        }

        $masterRow = [int]$master.Row
        $masterColumn = [int]$master.Column
        $fullRows = $fullArray.Rows
        $fullColumns = $fullArray.Columns
        $fullFirstRow = [int]$fullArray.Row
        $fullFirstColumn = [int]$fullArray.Column
        $fullLastRow = $fullFirstRow + [int]$fullRows.Count - 1
        $fullLastColumn = $fullFirstColumn + [int]$fullColumns.Count - 1
        if (
            $masterRow -lt $fullFirstRow -or $masterRow -gt $fullLastRow -or
            $masterColumn -lt $fullFirstColumn -or $masterColumn -gt $fullLastColumn
        ) {
            throw "Spill master $sheetName!$masterAddress is outside reset range $fullArrayAddress"
        }

        $cells = $fullArray.Cells
        $nonemptyFormulaCount = 0
        for ($cellIndex = 1; $cellIndex -le [int]$cells.Count; $cellIndex++) {
            $cell = $null
            $currentArray = $null
            $currentArrayRows = $null
            $currentArrayColumns = $null
            $spillParent = $null
            try {
                $cell = $cells.Item($cellIndex)
                if (-not [bool]$cell.HasFormula) {
                    continue
                }

                $cellFormula2 = ''
                try { $cellFormula2 = [string]$cell.Formula2 } catch {}
                $cellFormula = [string]$cell.Formula
                $substantiveFormula = if (-not [string]::IsNullOrWhiteSpace($cellFormula2)) {
                    $cellFormula2
                }
                else {
                    $cellFormula
                }

                $cellRow = [int]$cell.Row
                $cellColumn = [int]$cell.Column
                if (-not [string]::IsNullOrWhiteSpace($substantiveFormula)) {
                    $nonemptyFormulaCount++
                    if ($cellRow -ne $masterRow -or $cellColumn -ne $masterColumn) {
                        throw "Refusing to reset an unrelated nonempty formula in $sheetName!$fullArrayAddress at offset $cellIndex"
                    }
                    continue
                }

                # Empty <f ca=1/> cells are safe only when Excel can tie the
                # follower to the declared master via CurrentArray or SpillParent.
                $tiedToMaster = $false
                try {
                    $currentArray = $cell.CurrentArray
                    $currentArrayRows = $currentArray.Rows
                    $currentArrayColumns = $currentArray.Columns
                    $arrayFirstRow = [int]$currentArray.Row
                    $arrayFirstColumn = [int]$currentArray.Column
                    $arrayLastRow = $arrayFirstRow + [int]$currentArrayRows.Count - 1
                    $arrayLastColumn = $arrayFirstColumn + [int]$currentArrayColumns.Count - 1
                    if (
                        $arrayFirstRow -eq $masterRow -and
                        $arrayFirstColumn -eq $masterColumn -and
                        $arrayFirstRow -ge $fullFirstRow -and
                        $arrayFirstColumn -ge $fullFirstColumn -and
                        $arrayLastRow -le $fullLastRow -and
                        $arrayLastColumn -le $fullLastColumn
                    ) {
                        $tiedToMaster = $true
                    }
                }
                catch {
                    # Dynamic arrays may expose SpillParent instead of CurrentArray.
                }
                if (-not $tiedToMaster) {
                    try {
                        $spillParent = $cell.SpillParent
                        if (
                            [int]$spillParent.Row -eq $masterRow -and
                            [int]$spillParent.Column -eq $masterColumn
                        ) {
                            $tiedToMaster = $true
                        }
                    }
                    catch {
                        # The explicit failure below is safer than clearing an unproven formula.
                    }
                }
                if (-not $tiedToMaster) {
                    throw "Refusing to clear an empty formula cell that is not tied to spill master $sheetName!$masterAddress (offset $cellIndex)"
                }
            }
            finally {
                Release-Com $spillParent
                Release-Com $currentArrayColumns
                Release-Com $currentArrayRows
                Release-Com $currentArray
                Release-Com $cell
            }
        }
        if ($nonemptyFormulaCount -ne 1) {
            throw "Expected exactly one nonempty formula in $sheetName!$fullArrayAddress; found $nonemptyFormulaCount"
        }

        # The complete current-array envelope is selected, so Excel never sees a
        # request to modify only part of an array. ClearContents preserves formatting.
        $fullArray.ClearContents()
        Set-Formula $master $masterFormula2 $masterFormula
        Write-Log "Reset complete spill array: $sheetName!$fullArrayAddress; restored master $masterAddress"
    }
    finally {
        Release-Com $cells
        Release-Com $fullColumns
        Release-Com $fullRows
        Release-Com $fullArray
        Release-Com $master
        Release-Com $worksheet
    }
}

function Assert-CellNonBlank(
    $workbook,
    [string]$sheetName,
    [string]$address,
    [string]$expectedValue = ''
) {
    $worksheet = $null
    $cell = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $cell = $worksheet.Range($address)
        $text = [string]$cell.Text
        $value = [string]$cell.Value2
        if (
            [string]::IsNullOrWhiteSpace($value) -or
            $text.StartsWith('#') -or
            $text -match $script:TransientPattern
        ) {
            throw "Expected spill endpoint is blank or invalid: $sheetName!$address = $text"
        }
        if (
            -not [string]::IsNullOrWhiteSpace($expectedValue) -and
            $value.Trim() -ne $expectedValue
        ) {
            throw "Unexpected spill endpoint identifier: $sheetName!$address = [$value], expected [$expectedValue]"
        }
        Write-Log "Validated spill endpoint: $sheetName!$address=$value"
    }
    finally {
        Release-Com $cell
        Release-Com $worksheet
    }
}

function Assert-CellDateEqualsToday(
    $workbook,
    [string]$sheetName,
    [string]$address
) {
    $worksheet = $null
    $cell = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $cell = $worksheet.Range($address)
        $value = $cell.Value2
        if (-not (Test-IsNumeric $value)) {
            throw "Expected a numeric Excel date: $sheetName!$address = $([string]$cell.Text)"
        }
        $actualDate = [DateTime]::FromOADate([double]$value).Date
        $today = [DateTime]::Today
        if ($actualDate -ne $today) {
            throw "Expected today's date at $sheetName!${address}: actual=$($actualDate.ToString('yyyy-MM-dd')) expected=$($today.ToString('yyyy-MM-dd'))"
        }
        Write-Log "Validated current-price date anchor: $sheetName!$address=$($actualDate.ToString('yyyy-MM-dd'))"
    }
    finally {
        Release-Com $cell
        Release-Com $worksheet
    }
}

function Assert-CachedDateAnchorFresh(
    $workbook,
    [string]$sheetName,
    [string]$address,
    [int]$maximumAgeDays = 10
) {
    $worksheet = $null
    $cell = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $cell = $worksheet.Range($address)
        $value = $cell.Value2
        if (-not (Test-IsNumeric $value)) {
            throw "Expected a numeric cached Excel date: $sheetName!$address = $([string]$cell.Text)"
        }
        $cachedDate = [DateTime]::FromOADate([double]$value).Date
        $today = [DateTime]::Today
        $ageDays = [int](($today - $cachedDate).TotalDays)
        if ($ageDays -lt 0 -or $ageDays -gt $maximumAgeDays) {
            throw (
                "Cached price date is outside the permitted age: " +
                "$sheetName!${address}=$($cachedDate.ToString('yyyy-MM-dd')) " +
                "ageDays=$ageDays maximum=$maximumAgeDays"
            )
        }
        Write-Log (
            "Validated cached price as-of anchor without recalculation: " +
            "$sheetName!${address}=$($cachedDate.ToString('yyyy-MM-dd')) ageDays=$ageDays"
        )
    }
    finally {
        Release-Com $cell
        Release-Com $worksheet
    }
}

function Assert-TrimmedCells(
    $workbook,
    [string]$sheetName,
    [string[]]$addresses
) {
    $worksheet = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        foreach ($address in $addresses) {
            $cell = $null
            try {
                $cell = $worksheet.Range($address)
                $value = [string]$cell.Value2
                if ([string]::IsNullOrWhiteSpace($value) -or $value -ne $value.Trim()) {
                    throw "Expected a nonblank trimmed identifier: $sheetName!$address = [$value]"
                }
                Write-Log "Validated trimmed identifier: $sheetName!$address=$value"
            }
            finally {
                Release-Com $cell
            }
        }
    }
    finally {
        Release-Com $worksheet
    }
}

function Invoke-LocalRangeCalculation(
    $workbook,
    [string]$sheetName,
    [string]$address
) {
    Assert-BeforeDeadline "$sheetName!$address downstream calculation"
    $worksheet = $null
    $range = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $range = $worksheet.Range($address)
        Assert-NoBloombergFormula $range "$sheetName!$address"
        try {
            $range.Dirty()
        }
        catch {
            Write-Log "Range.Dirty was unavailable for downstream range $sheetName!${address}: $($_.Exception.Message)"
        }
        [void]$range.Calculate()
        Write-Log "Calculated downstream range: $sheetName!$address"
    }
    finally {
        Release-Com $range
        Release-Com $worksheet
    }
}

function Get-FxLastRefreshRow(
    $workbook,
    [string]$sheetName,
    [int]$firstNewRow,
    [int]$maximumRow = 735
) {
    $worksheet = $null
    $previousCell = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $previousCell = $worksheet.Range('A' + ($firstNewRow - 1))
        $previousValue = $previousCell.Value2
        if (-not (Test-IsNumeric $previousValue)) {
            throw "$sheetName!A$($firstNewRow - 1) is not a numeric Excel date"
        }
        $previousDate = [DateTime]::FromOADate([double]$previousValue).Date
        $today = [DateTime]::Today
        if ($previousDate -gt $today) {
            throw "$sheetName history ends in the future: $previousDate"
        }
        $newDateCount = [int]($today - $previousDate).TotalDays
        if ($newDateCount -eq 0) {
            return ($firstNewRow - 1)
        }
        $lastRow = ($firstNewRow - 1) + $newDateCount
        if ($lastRow -gt $maximumRow) {
            throw "$sheetName requires row $lastRow to reach today, beyond the prepared maximum row $maximumRow"
        }
        return $lastRow
    }
    finally {
        Release-Com $previousCell
        Release-Com $worksheet
    }
}

function Set-FxCurrentFallbackFormulas(
    $workbook,
    [string]$sheetName
) {
    Assert-BeforeDeadline "$sheetName!B6:L6 current-FX formula hardening"
    $worksheet = $null
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        for ($columnIndex = 2; $columnIndex -le 12; $columnIndex++) {
            $cell = $null
            try {
                $columnName = [string][char][int](64 + $columnIndex)
                $header = $columnName + '$5'
                $history = $columnName + '$8:' + $columnName + '$735'
                $formula = '=IF(NOT(ISTEXT(' + $header + ')),"",IF(OR(TRIM(' +
                    $header + ')="",TRIM(' + $header + ')="-"),"",LET(' +
                    'x,BDP(' + $header + ',"PX_LAST"),' +
                    'd,$A$8:$A$735,' +
                    'r,' + $history + ',' +
                    'ok,(d<=TODAY())*ISNUMBER(r),' +
                    'ld,LOOKUP(2,1/ok,d),' +
                    'lr,LOOKUP(2,1/ok,r),' +
                    'IF(ISNUMBER(x),x,IF(TODAY()-ld<=10,lr,NA())))))'
                $cell = $worksheet.Range($columnName + '6')
                Set-Formula $cell $formula $formula
            }
            finally {
                Release-Com $cell
            }
        }
        Write-Log "Hardened current FX formulas with a 10-day Bloomberg-history fallback: $sheetName!B6:L6"
    }
    finally {
        Release-Com $worksheet
    }
}

function Get-EquityLastActiveRow($workbook) {
    $worksheet = $null
    $rows = $null
    $cells = $null
    $bottomTickerCell = $null
    $lastTickerCell = $null
    $row21Cell = $null
    $row22Cell = $null
    try {
        $worksheet = $workbook.Worksheets.Item('Equity Transactions')
        $rows = $worksheet.Rows
        $cells = $worksheet.Cells
        $bottomTickerCell = $cells.Item([int]$rows.Count, 4)
        $lastTickerCell = $bottomTickerCell.End(-4162) # xlUp
        $lastActiveRow = [int]$lastTickerCell.Row
        if ($lastActiveRow -lt 9 -or $lastActiveRow -gt 995) {
            throw "Unexpected Equity Transactions active-row boundary: $lastActiveRow"
        }

        for ($row = 9; $row -le $lastActiveRow; $row++) {
            $tickerCell = $null
            try {
                $tickerCell = $worksheet.Range("D$row")
                $ticker = ([string]$tickerCell.Value2).Trim()
                if ([string]::IsNullOrWhiteSpace($ticker)) {
                    throw "Blank ticker inside active Equity Transactions range: D$row"
                }
            }
            finally {
                Release-Com $tickerCell
            }
        }

        $row21Cell = $worksheet.Range('D21')
        $row22Cell = $worksheet.Range('D22')
        $row21Ticker = ([string]$row21Cell.Value2).Trim()
        $row22Ticker = ([string]$row22Cell.Value2).Trim()
        if ($lastActiveRow -ne 21) {
            throw "Expected the last active equity transaction at row 21; found row $lastActiveRow"
        }
        if ($row21Ticker -ne 'BMW GR EQUITY') {
            throw "Unexpected final active equity ticker: Equity Transactions!D21=[$row21Ticker]"
        }
        if (-not [string]::IsNullOrWhiteSpace($row22Ticker)) {
            throw "Expected Equity Transactions!D22 to be blank; found [$row22Ticker]"
        }
        Write-Log 'Validated active equity transaction boundary: D21=BMW GR EQUITY; D22 blank'
        return $lastActiveRow
    }
    finally {
        Release-Com $row22Cell
        Release-Com $row21Cell
        Release-Com $lastTickerCell
        Release-Com $bottomTickerCell
        Release-Com $cells
        Release-Com $rows
        Release-Com $worksheet
    }
}

function Repair-BondCurrentPriceFormulas($workbook) {
    $worksheet = $null
    try {
        $worksheet = $workbook.Worksheets.Item('Bond Transactions')
        for ($row = 50; $row -le 156; $row++) {
            $cell = $null
            try {
                $formula = '=IF(NOT(ISTEXT($F' + $row + ')),"",IF(OR(TRIM($F' +
                    $row + ')="",TRIM($F' + $row + ')="-"),"",LET(' +
                    'p,IFERROR(INDEX(''Bond prices''!$B$16:$BE$16,1,MATCH($F' + $row +
                    ',''Bond prices''!$B$5:$BE$5,0)),NA()),' +
                    'IF(ISNUMBER(p),p%,NA()))))'
                $cell = $worksheet.Range("U$row")
                Set-Formula $cell $formula $formula
            }
            finally {
                Release-Com $cell
            }
        }
        Write-Log 'Repaired direct current-bond price lookups: Bond Transactions!U50:U156'
    }
    finally {
        Release-Com $worksheet
    }
}

function Repair-EquityCurrentPriceFormulas(
    $workbook,
    [int]$lastActiveRow
) {
    $transactions = $null
    $currentPositions = $null
    try {
        $transactions = $workbook.Worksheets.Item('Equity Transactions')
        for ($row = 9; $row -le $lastActiveRow; $row++) {
            $cell = $null
            try {
                $formula = '=IF(NOT(ISTEXT($D' + $row + ')),"",IF(OR(TRIM($D' +
                    $row + ')="",TRIM($D' + $row + ')="-",$Z' + $row + '=""),"",LET(' +
                    'p,IFERROR(INDEX(''Equity prices''!$B$7:$K$7,1,MATCH($D' + $row +
                    ',''Equity prices''!$B$4:$K$4,0)),NA()),' +
                    'IF(ISNUMBER(p),IF($Z' + $row + '="GBp",p/100,p),NA()))))'
                $cell = $transactions.Range("AC$row")
                Set-Formula $cell $formula $formula
            }
            finally {
                Release-Com $cell
            }
        }

        $currentPositions = $workbook.Worksheets.Item('Current Equity Positions')
        for ($row = 4; $row -le 13; $row++) {
            $cell = $null
            try {
                $formula = '=IF(NOT(ISTEXT($B' + $row + ')),"",IF(OR(TRIM($B' +
                    $row + ')="",TRIM($B' + $row + ')="-",$D' + $row + '=""),"",LET(' +
                    'p,IFERROR(INDEX(''Equity prices''!$B$7:$K$7,1,MATCH($B' + $row +
                    ',''Equity prices''!$B$4:$K$4,0)),NA()),' +
                    'IF(ISNUMBER(p),IF($D' + $row + '="GBp",p/100,p),NA()))))'
                $cell = $currentPositions.Range("E$row")
                Set-Formula $cell $formula $formula
            }
            finally {
                Release-Com $cell
            }
        }
        Write-Log (
            "Repaired direct current-equity price lookups: " +
            "Equity Transactions!AC9:AC$lastActiveRow; Current Equity Positions!E4:E13"
        )
    }
    finally {
        Release-Com $currentPositions
        Release-Com $transactions
    }
}

function Repair-EquityFxFormulas(
    $workbook,
    [int]$lastActiveRow
) {
    $worksheet = $null
    try {
        $worksheet = $workbook.Worksheets.Item('Equity Transactions')
        for ($row = 9; $row -le $lastActiveRow; $row++) {
            $historicalCell = $null
            $currentCell = $null
            try {
                $historicalFormula = '=IF(OR($Z' + $row + '="",$A' + $row + '=""),"",IF($Z' +
                    $row + '="USD",1,LET(' +
                    'd,''Exchange rate - base USD''!$A$8:$A$735,' +
                    'c,MATCH($Z' + $row + ',''Exchange rate - base USD''!$B$4:$L$4,0),' +
                    'r,INDEX(''Exchange rate - base USD''!$B$8:$L$735,0,c),' +
                    'ok,(d<=$A' + $row + ')*ISNUMBER(r),' +
                    'ld,LOOKUP(2,1/ok,d),' +
                    'lr,LOOKUP(2,1/ok,r),' +
                    'IF($A' + $row + '-ld<=10,lr,NA()))))'
                $currentFormula = '=IF($Z' + $row + '="","",IF($Z' + $row + '="USD",1,LET(' +
                    'c,MATCH($Z' + $row + ',''Exchange rate - base USD''!$B$4:$L$4,0),' +
                    'live,INDEX(''Exchange rate - base USD''!$B$6:$L$6,1,c),' +
                    'd,''Exchange rate - base USD''!$A$8:$A$735,' +
                    'r,INDEX(''Exchange rate - base USD''!$B$8:$L$735,0,c),' +
                    'ok,(d<=TODAY())*ISNUMBER(r),' +
                    'ld,LOOKUP(2,1/ok,d),' +
                    'lr,LOOKUP(2,1/ok,r),' +
                    'IF(ISNUMBER(live),live,IF(TODAY()-ld<=10,lr,NA())))))'
                $historicalCell = $worksheet.Range("AF$row")
                $currentCell = $worksheet.Range("AG$row")
                Set-Formula $historicalCell $historicalFormula $historicalFormula
                Set-Formula $currentCell $currentFormula $currentFormula
            }
            finally {
                Release-Com $currentCell
                Release-Com $historicalCell
            }
        }
        Write-Log "Repaired Equity Transactions historical/current FX formulas: AF9:AG$lastActiveRow"
    }
    finally {
        Release-Com $worksheet
    }
}

function Limit-SummarySumFormulas(
    $workbook,
    [string]$sheetName,
    [string]$summaryAddress,
    [int]$lastActiveRow
) {
    $worksheet = $null
    $summaryRange = $null
    $cells = $null
    $changed = 0
    try {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $summaryRange = $worksheet.Range($summaryAddress)
        $cells = $summaryRange.Cells
        for ($cellIndex = 1; $cellIndex -le [int]$cells.Count; $cellIndex++) {
            $cell = $null
            try {
                $cell = $cells.Item($cellIndex)
                if (-not [bool]$cell.HasFormula) {
                    continue
                }
                $formula2 = ''
                try { $formula2 = [string]$cell.Formula2 } catch {}
                $formula = [string]$cell.Formula
                $candidate = if (-not [string]::IsNullOrWhiteSpace($formula2)) { $formula2 } else { $formula }
                $match = [regex]::Match($candidate, '^=SUM\(([A-Z]{1,3})\$9:\1\$[0-9]+\)$', 'IgnoreCase')
                if (-not $match.Success) {
                    continue
                }
                $columnName = $match.Groups[1].Value.ToUpperInvariant()
                $newFormula = '=SUM(' + $columnName + '$9:' + $columnName + '$' + $lastActiveRow + ')'
                Set-Formula $cell $newFormula $newFormula
                $changed++
            }
            finally {
                Release-Com $cell
            }
        }
        if ($changed -eq 0) {
            throw "No summary SUM formulas were limited in $sheetName!$summaryAddress"
        }
        Write-Log "Limited summary formulas to active rows in $sheetName!${summaryAddress}: changed=$changed lastRow=$lastActiveRow"
    }
    finally {
        Release-Com $cells
        Release-Com $summaryRange
        Release-Com $worksheet
    }
}

function Get-BondPriceLastColumn($workbook) {
    $worksheet = $null
    $cells = $null
    $columns = $null
    $anchor = $null
    $lastCell = $null
    try {
        $worksheet = $workbook.Worksheets.Item('Bond prices')
        $cells = $worksheet.Cells
        $columns = $worksheet.Columns
        $anchor = $cells.Item(4, [int]$columns.Count)
        $lastCell = $anchor.End(-4159) # xlToLeft
        $lastColumn = [int]$lastCell.Column
        if ($lastColumn -lt 2) {
            throw 'No populated bond securities were found in Bond prices row 4'
        }
        $columnName = ''
        $remaining = [int]$lastColumn
        while ($remaining -gt 0) {
            $remaining--
            $columnName = [char][int](65 + ($remaining % 26)) + $columnName
            $remaining = [int][Math]::Floor($remaining / 26)
        }
        return $columnName
    }
    finally {
        Release-Com $lastCell
        Release-Com $anchor
        Release-Com $columns
        Release-Com $cells
        Release-Com $worksheet
    }
}

function Assert-OnlyTargetWorkbookOpen($workbooks, [string]$targetPath) {
    $count = [int]$workbooks.Count
    for ($index = 1; $index -le $count; $index++) {
        $candidate = $null
        $isTargetWorkbook = $false
        try {
            $candidate = $workbooks.Item($index)
            $candidatePath = [IO.Path]::GetFullPath([string]$candidate.FullName)
            if ($candidatePath -eq $targetPath) {
                # Excel returns the same RCW for this lookup as for $workbook.
                # FinalReleaseComObject here would invalidate the caller's live
                # workbook reference. Let the temporary reference fall out of
                # scope and release the workbook once in the outer finally block.
                $isTargetWorkbook = $true
                continue
            }
            if ([bool]$candidate.IsAddin) {
                Write-Log "Permitting Excel add-in workbook in isolated process: $candidatePath"
                continue
            }
            throw "Unexpected non-add-in workbook opened in isolated Excel process: $candidatePath"
        }
        finally {
            if (-not $isTargetWorkbook) {
                Release-Com $candidate
            }
        }
    }
}

function Get-KeySnapshot($workbook) {
    $specs = @(
        @('Transactions List', 'Q245'),
        @('Transactions List', 'U231'),
        @('Transactions List', 'V231'),
        @('Transactions List', 'Z226'),
        @('Bond Transactions', 'BD141'),
        @('Bond Transactions', 'BG141'),
        @('BS P&L', 'G26'),
        @('BS P&L', 'G49'),
        @('BS P&L', 'D33'),
        @('Bonds maturity and cpn timeline', 'X9')
    )
    $parts = New-Object Collections.Generic.List[string]
    foreach ($spec in $specs) {
        $worksheet = $null
        $cell = $null
        try {
            $worksheet = $workbook.Worksheets.Item($spec[0])
            $cell = $worksheet.Range($spec[1])
            $parts.Add($spec[0] + '!' + $spec[1] + '=' + [string]$cell.Text)
        }
        finally {
            Release-Com $cell
            Release-Com $worksheet
        }
    }
    return ($parts -join '|')
}

function Get-PnlDiagnosticSnapshot($workbook) {
    $worksheet = $null
    $parts = New-Object Collections.Generic.List[string]
    try {
        $worksheet = $workbook.Worksheets.Item('BS P&L')
        for ($row = 8; $row -le 49; $row++) {
            $fCell = $null
            $gCell = $null
            $hCell = $null
            try {
                $fCell = $worksheet.Range("F$row")
                $gCell = $worksheet.Range("G$row")
                $hCell = $worksheet.Range("H$row")
                $fText = [string]$fCell.Text
                $gText = [string]$gCell.Text
                $hText = [string]$hCell.Text
                if (
                    -not [string]::IsNullOrWhiteSpace($fText) -or
                    -not [string]::IsNullOrWhiteSpace($gText) -or
                    -not [string]::IsNullOrWhiteSpace($hText)
                ) {
                    $parts.Add("row$row F=[$fText] G=[$gText] H=[$hText]")
                }
            }
            finally {
                Release-Com $hCell
                Release-Com $gCell
                Release-Com $fCell
            }
        }
    }
    finally {
        Release-Com $worksheet
    }
    return ($parts -join '; ')
}

function Assert-CriticalCells($workbook) {
    $numericSpecs = @(
        @('Transactions List', 'Q245'),
        @('Transactions List', 'U231'),
        @('Transactions List', 'V231'),
        @('Transactions List', 'Z226'),
        @('Bond Transactions', 'BD141'),
        @('Bond Transactions', 'BG141'),
        @('BS P&L', 'G26'),
        @('BS P&L', 'G49'),
        @('BS P&L', 'D33'),
        @('Bonds maturity and cpn timeline', 'X9')
    )
    foreach ($spec in $numericSpecs) {
        $worksheet = $null
        $cell = $null
        try {
            $worksheet = $workbook.Worksheets.Item($spec[0])
            $cell = $worksheet.Range($spec[1])
            $text = [string]$cell.Text
            $value = $cell.Value2
            if ($text -match $script:TransientPattern -or $text.StartsWith('#') -or -not (Test-IsNumeric $value)) {
                throw "Critical cell is not numeric: $($spec[0])!$($spec[1]) = $text"
            }
        }
        finally {
            Release-Com $cell
            Release-Com $worksheet
        }
    }
}

Write-Status 'starting'
Write-Log ('=' * 72)
Write-Log "Starting targeted Bloomberg refresh: $resolvedWorkbook"
Write-Log "Hard deadline: $($script:RunDeadline.ToString('yyyy-MM-dd HH:mm:ss'))"

$excel = $null
$workbooks = $null
$workbook = $null
$dummyWorkbook = $null
$ownsExcel = $false
$excelPid = 0

try {
    if (-not ('WolfTargetedExcelPid' -as [type])) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class WolfTargetedExcelPid {
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
'@
    }

    $existingExcelPids = @(Get-Process -Name EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $excel = New-Object -ComObject Excel.Application
    [uint32]$newPid = 0
    [void][WolfTargetedExcelPid]::GetWindowThreadProcessId([IntPtr]$excel.Hwnd, [ref]$newPid)
    $excelPid = [int]$newPid
    if ($excelPid -le 0) {
        throw 'Could not resolve the Excel process ID for the COM instance'
    }
    if ($existingExcelPids -contains $excelPid) {
        throw "Excel COM reused a pre-existing Excel process ($excelPid); no workbook was opened and the process will not be quit"
    }
    $ownsExcel = $true
    Write-Log "Created isolated Excel process PID=$excelPid"
    Write-Status "opening: pid=$excelPid"

    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AskToUpdateLinks = $false
    $excel.EnableEvents = $false
    $excel.ScreenUpdating = $false
    $excel.AutomationSecurity = 3
    $workbooks = $excel.Workbooks
    # Excel may reject Calculation changes when it has no workbook. The temporary
    # unsaved workbook is never a file and is closed immediately after the target opens.
    $dummyWorkbook = $workbooks.Add()
    $excel.Calculation = -4135 # xlCalculationManual
    $excel.CalculateBeforeSave = $false

    Assert-BeforeDeadline 'opening repaired workbook'
    $workbook = $workbooks.Open($resolvedWorkbook, 0, $false)
    if ([IO.Path]::GetFullPath([string]$workbook.FullName) -ne $resolvedWorkbook) {
        throw "Excel opened the wrong workbook: $($workbook.FullName)"
    }
    if ([bool]$workbook.ReadOnly) {
        throw 'The repaired workbook opened read-only; targeted refresh cannot save safely'
    }
    $dummyWorkbook.Close($false)
    Release-Com $dummyWorkbook
    $dummyWorkbook = $null
    Assert-OnlyTargetWorkbookOpen $workbooks $resolvedWorkbook

    $bloombergAddin = $null
    try {
        $bloombergAddin = $excel.COMAddIns.Item('Bofaddin.Connect')
        if (-not [bool]$bloombergAddin.Connect) {
            throw 'Bloomberg COM add-in Bofaddin.Connect is not connected in the isolated Excel process'
        }
    }
    finally {
        Release-Com $bloombergAddin
    }
    Write-Log 'Bloomberg COM add-in is connected'

    Write-Status "rebuilding-spills: pid=$excelPid"
    # A manual Excel open can invalidate cached dynamic-array followers and
    # leave empty follower formula records or blocking cached constants. Each
    # reset snapshots its local master, proves that no other substantive formula
    # occupies the known spill envelope, clears the complete envelope (which
    # preserves formatting), and restores only the master formula.
    Reset-DerivedSpillArray $workbook 'Bond Transactions' 'D50' 'D50:D156'
    Invoke-LocalRangeCalculation $workbook 'Bond Transactions' 'D50'
    Assert-CellNonBlank $workbook 'Bond Transactions' 'D141' 'US500769JZ83'
    Assert-TrimmedCells $workbook 'Bond Transactions' @('D74', 'D75', 'D77', 'D95')

    Reset-DerivedSpillArray $workbook 'Bonds analysis' 'A5' 'A5:A63'
    Invoke-LocalRangeCalculation $workbook 'Bonds analysis' 'A5'
    # The four repaired whitespace IDs collapse three false UNIQUE entries,
    # so the normalized 56-security list ends at A60 (not the cached A63).
    Assert-CellNonBlank $workbook 'Bonds analysis' 'A60' 'US500769JZ83'

    Reset-DerivedSpillArray $workbook 'Bond prices' 'B4' 'B4:BH4'
    Invoke-LocalRangeCalculation $workbook 'Bond prices' 'B4'
    Assert-CellNonBlank $workbook 'Bond prices' 'BE4' 'US500769JZ83'
    Invoke-LocalRangeCalculation $workbook 'Bond prices' 'A30'
    Assert-CellNonBlank $workbook 'Bond prices' 'A86' 'US500769JZ83'
    $bondLastColumn = Get-BondPriceLastColumn $workbook
    Write-Log "Rebuilt bond-security spills through Bond prices column $bondLastColumn"

    Reset-DerivedSpillArray $workbook 'Equity prices' 'B4' 'B4:K4'
    Invoke-LocalRangeCalculation $workbook 'Equity prices' 'B4'
    Assert-CellNonBlank $workbook 'Equity prices' 'K4' 'BMW GR EQUITY'
    $equityLastActiveRow = Get-EquityLastActiveRow $workbook
    Write-Log 'Rebuilt the 10-security equity-price header spill through column K'

    Write-Status "refreshing-bloomberg: pid=$excelPid"

    # Date rows are local formulas. Calculate only rows needed to reach today,
    # then refresh their Bloomberg rate cells; future prepared rows remain untouched.
    $sgdLastRow = Get-FxLastRefreshRow $workbook 'Exchange rate - base SGD' 556
    $usdLastRow = Get-FxLastRefreshRow $workbook 'Exchange rate - base USD' 598
    if ($sgdLastRow -ge 556) {
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Exchange rate - base SGD' "A556:A$sgdLastRow" 'NumericOnly' 0 2)
    }
    if ($usdLastRow -ge 598) {
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Exchange rate - base USD' "A598:A$usdLastRow" 'NumericOnly' 0 2)
    }
    Write-Log "FX target rows through today: SGD=$sgdLastRow USD=$usdLastRow"

    if ($UseCachedProviderEvidence) {
        # The earlier bounded full-rebuild attempt successfully populated both
        # FX extensions through today before legacy requests stalled. Preserve
        # those licensed observations and validate them without issuing more
        # Bloomberg calls. Current prices and J64 likewise retain their last
        # numeric provider caches; formulas remain live for the next user open.
        Write-Log 'Bloomberg live requests are unavailable; using validated cached provider evidence'
        Assert-CachedDateAnchorFresh $workbook 'Bond prices' 'A16' 10
        Assert-CachedDateAnchorFresh $workbook 'Equity prices' 'A7' 10
        if ($sgdLastRow -ge 556) {
            [void](Assert-CachedRangeState $workbook 'Exchange rate - base SGD' "B556:L$sgdLastRow" 'NumericOrNoData')
        }
        if ($usdLastRow -ge 598) {
            [void](Assert-CachedRangeState $workbook 'Exchange rate - base USD' "B598:L$usdLastRow" 'NumericOrNoData')
        }
        [void](Assert-CachedRangeState $workbook 'Bond prices' "B16:$($bondLastColumn)16" 'NumericOnly')
        [void](Assert-CachedRangeState $workbook 'Equity prices' 'B7:K7' 'NumericOnly')
        [void](Assert-CachedRangeState $workbook 'Cash Transactions - analysis' 'J64' 'NumericOnly')

        Set-FxCurrentFallbackFormulas $workbook 'Exchange rate - base SGD'
        Set-FxCurrentFallbackFormulas $workbook 'Exchange rate - base USD'
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Exchange rate - base SGD' 'B6:L6' 'NumericOnly' 0 2)
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Exchange rate - base USD' 'B6:L6' 'NumericOnly' 0 2)
    }
    else {
        # Only a live provider run may advance the price as-of anchors to today.
        Invoke-LocalRangeCalculation $workbook 'Bond prices' 'A16'
        Assert-CellDateEqualsToday $workbook 'Bond prices' 'A16'
        Invoke-LocalRangeCalculation $workbook 'Equity prices' 'A7'
        Assert-CellDateEqualsToday $workbook 'Equity prices' 'A7'

        # Refresh historical observations first. The current-rate formulas below
        # then use live BDP when numeric and otherwise fall back to today's most
        # recent numeric BDH observation (with a 10-day maximum carry).
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Exchange rate - base USD' 'K8:K30' 'NumericOrNoData' 10)
        if ($sgdLastRow -ge 556) {
            [void](Invoke-TargetedRangeCalculation $workbook $excel 'Exchange rate - base SGD' "B556:L$sgdLastRow" 'NumericOrNoData' 10)
        }
        if ($usdLastRow -ge 598) {
            [void](Invoke-TargetedRangeCalculation $workbook $excel 'Exchange rate - base USD' "B598:L$usdLastRow" 'NumericOrNoData' 10)
        }
        Set-FxCurrentFallbackFormulas $workbook 'Exchange rate - base SGD'
        Set-FxCurrentFallbackFormulas $workbook 'Exchange rate - base USD'
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Exchange rate - base SGD' 'B6:L6' 'NumericOnly' 10)
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Exchange rate - base USD' 'B6:L6' 'NumericOnly' 10)

        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Bond prices' "B1:$($bondLastColumn)1" 'NumericOnly' 0 2)
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Bond prices' "B16:$($bondLastColumn)16" 'NumericOnly' 10)
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Equity prices' 'B7:K7' 'NumericOnly' 10)
        [void](Invoke-TargetedRangeCalculation $workbook $excel 'Cash Transactions - analysis' 'J64' 'NumericOnly' 10)
    }

    Repair-BondCurrentPriceFormulas $workbook
    Repair-EquityCurrentPriceFormulas $workbook $equityLastActiveRow
    Repair-EquityFxFormulas $workbook $equityLastActiveRow
    Limit-SummarySumFormulas $workbook 'Equity Transactions' 'AI4:CE4' $equityLastActiveRow
    Limit-SummarySumFormulas $workbook 'Bond Transactions' 'AE4:CI4' 156

    Write-Status "calculating-downstream: pid=$excelPid"
    # Dependency order: transaction inputs -> FX conversions/cumulatives ->
    # asset-class valuations -> summaries -> cash/property rollups -> P&L.
    $downstreamRanges = @(
        @('Transactions List', 'F223'),
        @('Transactions List', 'Q2:Q246'),
        @('Transactions List', 'R2:R246'),
        @('Transactions List', 'S2:T246'),
        @('Transactions List', 'U2:U246'),
        @('Transactions List', 'V2:V246'),
        @('Transactions List', 'W2:X246'),
        @('Transactions List', 'Z211:Z246'),
        @('Transactions List', 'AA211:AC246'),
        @('Transactions List', 'AD211:AD246'),
        @('Transactions List', 'AE211:AG246'),
        @('Bond Transactions', 'A9:S156'),
        @('Bond Transactions', 'T9:AC156'),
        @('Bond Transactions', 'AE9:BA156'),
        @('Bond Transactions', 'BD9:BE156'),
        @('Bond Transactions', 'BG9:CC156'),
        @('Bond Transactions', 'CF9:CG156'),
        @('Bond Transactions', 'CI9:CI156'),
        @('Bond Transactions', 'AE4:CI6'),
        @('Current Bond Positions', 'A2:AK100'),
        @('Equity Transactions', "A9:AG$equityLastActiveRow"),
        @('Equity Transactions', "AI9:BA$equityLastActiveRow"),
        @('Equity Transactions', "BD9:BY$equityLastActiveRow"),
        @('Equity Transactions', "CB9:CE$equityLastActiveRow"),
        @('Equity Transactions', 'AI4:CE6'),
        @('Current Equity Positions', 'B1:E13'),
        @('Current Equity Positions', 'G1:S13'),
        @('Current Equity Positions', 'U1:AB13'),
        @('Current Equity Positions', 'AG1:AI13'),
        @('Cash Balances', 'A1:N69'),
        @('Properties', 'A1:P51'),
        @('Bonds maturity and cpn timeline', 'U9:X100'),
        @('BS P&L', 'B1:H51')
    )
    foreach ($spec in $downstreamRanges) {
        if ($spec[0] -eq 'Current Bond Positions') {
            Reset-DerivedSpillArray $workbook 'Current Bond Positions' 'A5' 'A5:A100'
            Invoke-LocalRangeCalculation $workbook 'Current Bond Positions' 'A5'
            Assert-CellNonBlank $workbook 'Current Bond Positions' 'A5'
            Invoke-LocalRangeCalculation $workbook 'Current Bond Positions' 'B2:AK100'
            continue
        }
        if ($spec[0] -eq 'Bonds maturity and cpn timeline') {
            Reset-DerivedSpillArray $workbook 'Bonds maturity and cpn timeline' 'U9' 'U9:U100'
            Invoke-LocalRangeCalculation $workbook 'Bonds maturity and cpn timeline' 'U9'
            Assert-CellNonBlank $workbook 'Bonds maturity and cpn timeline' 'U9'
            Invoke-LocalRangeCalculation $workbook 'Bonds maturity and cpn timeline' 'V9:X100'
            continue
        }
        Invoke-LocalRangeCalculation $workbook $spec[0] $spec[1]
    }

    $snapshot = Get-KeySnapshot $workbook
    Write-Log "Pre-validation critical snapshot: $snapshot"
    Write-Log ('P&L diagnostic: ' + (Get-PnlDiagnosticSnapshot $workbook))
    Assert-CriticalCells $workbook
    Write-Log "Critical cells validated: $snapshot"

    Assert-BeforeDeadline 'saving repaired workbook'
    $workbook.CheckCompatibility = $false
    # The structural repair marked the file for a full rebuild. This targeted
    # refresh has now resolved its explicit dependency chain, so do not leave a
    # future full-workbook recalculation armed.
    $workbook.ForceFullCalculation = $false
    try {
        $workbook.FullCalculationOnLoad = $false
    }
    catch {
        Write-Log "FullCalculationOnLoad is unavailable in this Excel COM build: $($_.Exception.Message)"
    }
    $workbook.Save()
    if (-not [bool]$workbook.Saved) {
        throw 'Excel did not report the repaired workbook as saved'
    }
    Write-Log 'Saved targeted Bloomberg refresh to repaired workbook'
    Write-Status "complete: pid=$excelPid; $snapshot"
    $script:Completed = $true
}
catch {
    Write-Log ('FAILED: ' + $_.Exception.Message)
    Write-Log ([string]$_.ScriptStackTrace)
    Write-Status ('failed: ' + $_.Exception.Message)
    throw
}
finally {
    if ($null -ne $dummyWorkbook) {
        try { $dummyWorkbook.Close($false) } catch {}
        Release-Com $dummyWorkbook
    }
    if ($null -ne $workbook) {
        try { $workbook.Close($false) } catch {}
        Release-Com $workbook
    }
    Release-Com $workbooks
    if ($null -ne $excel) {
        if ($ownsExcel) {
            try { $excel.Quit() } catch { Write-Log "Owned Excel Quit returned: $($_.Exception.Message)" }
        }
        Release-Com $excel
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()

    if ($ownsExcel -and $excelPid -gt 0) {
        $remaining = Get-Process -Id $excelPid -ErrorAction SilentlyContinue
        if ($null -ne $remaining) {
            Write-Log "Owned Excel PID=$excelPid remained after Quit; waiting up to five seconds"
            try { Wait-Process -Id $excelPid -Timeout 5 -ErrorAction SilentlyContinue } catch {}
            $remaining = Get-Process -Id $excelPid -ErrorAction SilentlyContinue
            if ($null -ne $remaining) {
                Write-Log "Force-stopping only the owned isolated Excel PID=$excelPid"
                Stop-Process -Id $excelPid -Force -ErrorAction SilentlyContinue
            }
        }
    }
    if (-not $script:Completed) {
        $currentStatus = Get-Content -LiteralPath $StatusPath -ErrorAction SilentlyContinue
        if ($null -eq $currentStatus -or [string]$currentStatus -notmatch '^failed:') {
            Write-Status 'failed: targeted refresh ended before completion'
        }
    }
}
