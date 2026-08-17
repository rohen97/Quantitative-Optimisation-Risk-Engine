param(
    [Parameter(Mandatory = $true)]
    [string]$WorkbookPath,
    [string]$StatusPath = "",
    [string]$LogPath = ""
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$resolvedWorkbook = [IO.Path]::GetFullPath($WorkbookPath)
if (-not (Test-Path -LiteralPath $resolvedWorkbook -PathType Leaf)) {
    throw "Workbook not found: $resolvedWorkbook"
}
if ([IO.Path]::GetExtension($resolvedWorkbook) -ne '.xlsx') {
    throw "Expected an .xlsx workbook: $resolvedWorkbook"
}
if ([string]::IsNullOrWhiteSpace($StatusPath)) {
    $StatusPath = [IO.Path]::ChangeExtension($resolvedWorkbook, '.status.txt')
}
if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = [IO.Path]::ChangeExtension($resolvedWorkbook, '.repair.log')
}

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

function Set-Formula($cell, [string]$formula) {
    try {
        $cell.Formula2 = $formula
    }
    catch {
        $cell.Formula = $formula
    }
}

function Get-HistoricalFxFormula(
    [int]$row,
    [string]$sheet,
    [string]$identityCurrency,
    [string]$currencyColumn,
    [string]$dateColumn
) {
    $currencyCell = '$' + $currencyColumn + $row
    $dateCell = '$' + $dateColumn + $row
    return '=IF(OR(' + $currencyCell + '="",' + $dateCell + '=""),"",IF(' +
        $currencyCell + '="' + $identityCurrency + '",1,LET(' +
        'd,''' + $sheet + '''!$A$8:$A$735,' +
        'c,MATCH(' + $currencyCell + ',''' + $sheet + '''!$B$4:$L$4,0),' +
        'r,INDEX(''' + $sheet + '''!$B$8:$L$735,0,c),' +
        'ok,(d<=' + $dateCell + ')*ISNUMBER(r),' +
        'ld,LOOKUP(2,1/ok,d),' +
        'lr,LOOKUP(2,1/ok,r),' +
        'IF(' + $dateCell + '-ld<=10,lr,NA()))))'
}

function Get-CurrentFxFormula(
    [int]$row,
    [string]$sheet,
    [string]$identityCurrency,
    [string]$currencyColumn
) {
    $currencyCell = '$' + $currencyColumn + $row
    return '=IF(' + $currencyCell + '="","",IF(' +
        $currencyCell + '="' + $identityCurrency + '",1,LET(' +
        'c,MATCH(' + $currencyCell + ',''' + $sheet + '''!$B$4:$L$4,0),' +
        'live,INDEX(''' + $sheet + '''!$B$6:$L$6,1,c),' +
        'd,''' + $sheet + '''!$A$8:$A$735,' +
        'r,INDEX(''' + $sheet + '''!$B$8:$L$735,0,c),' +
        'ok,(d<=TODAY())*ISNUMBER(r),' +
        'ld,LOOKUP(2,1/ok,d),' +
        'lr,LOOKUP(2,1/ok,r),' +
        'IF(ISNUMBER(live),live,IF(TODAY()-ld<=10,lr,NA())))))'
}

function For-Each-FormulaCell($worksheet, [scriptblock]$action) {
    $used = $null
    $formulaCells = $null
    try {
        $used = $worksheet.UsedRange
        try {
            $formulaCells = $used.SpecialCells(-4123) # xlCellTypeFormulas
        }
        catch {
            return
        }
        $areas = $formulaCells.Areas
        try {
            for ($areaIndex = 1; $areaIndex -le $areas.Count; $areaIndex++) {
                $area = $areas.Item($areaIndex)
                try {
                    $cells = $area.Cells
                    try {
                        for ($cellIndex = 1; $cellIndex -le $cells.Count; $cellIndex++) {
                            $cell = $cells.Item($cellIndex)
                            try {
                                & $action $cell
                            }
                            finally {
                                Release-Com $cell
                            }
                        }
                    }
                    finally {
                        Release-Com $cells
                    }
                }
                finally {
                    Release-Com $area
                }
            }
        }
        finally {
            Release-Com $areas
        }
    }
    finally {
        Release-Com $formulaCells
        Release-Com $used
    }
}

function Remove-ExternalFormulaReferences($workbook) {
    $script:WolfExternalReplacementCount = 0
    $sheetCount = $workbook.Worksheets.Count
    for ($sheetIndex = 1; $sheetIndex -le $sheetCount; $sheetIndex++) {
        $worksheet = $workbook.Worksheets.Item($sheetIndex)
        try {
            For-Each-FormulaCell $worksheet {
                param($cell)
                $formula = [string]$cell.Formula2
                if ($formula -notmatch '\[[^\]]+\.(xlsx|xlsm|xlsb|xls)\]') {
                    return
                }
                $newFormula = [regex]::Replace(
                    $formula,
                    "'[^']*\[[^\]]+\.(?:xlsx|xlsm|xlsb|xls)\]([^']+)'!",
                    { param($match) "'" + $match.Groups[1].Value + "'!" },
                    [Text.RegularExpressions.RegexOptions]::IgnoreCase
                )
                if ($newFormula -ne $formula) {
                    $script:WolfExternalReplacementCount++
                    Set-Formula $cell $newFormula
                }
            }
        }
        finally {
            Release-Com $worksheet
        }
    }
    return $script:WolfExternalReplacementCount
}

function Count-ExternalFormulaReferences($workbook) {
    $script:WolfExternalFormulaCount = 0
    $sheetCount = $workbook.Worksheets.Count
    for ($sheetIndex = 1; $sheetIndex -le $sheetCount; $sheetIndex++) {
        $worksheet = $workbook.Worksheets.Item($sheetIndex)
        try {
            For-Each-FormulaCell $worksheet {
                param($cell)
                if ([string]$cell.Formula2 -match '\[[^\]]+\.(xlsx|xlsm|xlsb|xls)\]') {
                    $script:WolfExternalFormulaCount++
                }
            }
        }
        finally {
            Release-Com $worksheet
        }
    }
    return $script:WolfExternalFormulaCount
}

function Guard-BloombergFormulas($workbook, [string[]]$sheetNames) {
    $script:WolfGuardedFormulaCount = 0
    foreach ($sheetName in $sheetNames) {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        try {
            For-Each-FormulaCell $worksheet {
                param($cell)
                $formula = [string]$cell.Formula2
                if ($formula -notmatch '(?i)\bBD[PH]\(') {
                    return
                }
                if ($formula -match '(?i)^=IF\(NOT\(ISTEXT\(') {
                    return
                }
                $match = [regex]::Match($formula, '(?i)\bBD[PH]\(\$?([A-Z]{1,3})\$?(\d+)')
                if (-not $match.Success) {
                    return
                }
                $securityCell = '$' + $match.Groups[1].Value + '$' + $match.Groups[2].Value
                $inner = $formula.Substring(1)
                $newFormula = '=IF(NOT(ISTEXT(' + $securityCell + ')),"",IF(OR(TRIM(' +
                    $securityCell + ')="",TRIM(' + $securityCell + ')="-"),"",' + $inner + '))'
                Set-Formula $cell $newFormula
                $script:WolfGuardedFormulaCount++
            }
        }
        finally {
            Release-Com $worksheet
        }
    }
    return $script:WolfGuardedFormulaCount
}

function Extend-FxSheet($workbook, [string]$sheetName, [int]$firstNewRow) {
    $worksheet = $workbook.Worksheets.Item($sheetName)
    try {
        $dateRange = $worksheet.Range("A$firstNewRow", 'A735')
        try {
            $dateRange.FormulaR1C1 = '=IF(R[-1]C="","",IF(R[-1]C<TODAY(),R[-1]C+1,""))'
        }
        finally {
            Release-Com $dateRange
        }

        $rateRange = $worksheet.Range("B$firstNewRow", 'L735')
        try {
            $rateRange.FormulaR1C1 = '=IF(OR(RC1="",R5C="",R5C="-"),"",BDH(R5C,"PX_LAST",RC1,RC1))'
        }
        finally {
            Release-Com $rateRange
        }

        $currentRange = $worksheet.Range('B6', 'L6')
        try {
            $currentRange.FormulaR1C1 = '=IF(NOT(ISTEXT(R5C)),"",IF(OR(TRIM(R5C)="",TRIM(R5C)="-"),"",LET(x,BDP(R5C,"PX_LAST"),IF(ISNUMBER(x),x,""))))'
        }
        finally {
            Release-Com $currentRange
        }
    }
    finally {
        Release-Com $worksheet
    }
}

function Repair-TransactionsList($workbook) {
    $worksheet = $workbook.Worksheets.Item('Transactions List')
    try {
        $lastCell = $worksheet.Cells.Item($worksheet.Rows.Count, 1).End(-4162) # xlUp
        try {
            $lastRow = [int]$lastCell.Row
        }
        finally {
            Release-Com $lastCell
        }
        if ($lastRow -ne 246) {
            throw "Unexpected Transactions List last populated row: $lastRow (expected 246)"
        }

        # These cells lost their standard Bloomberg formulas during an accidental paste.
        # Intentional manual/trade-confirmation cells Q9/Q39/Q42/Q45/Q49 are preserved.
        $restoreQRows = @(217, 218, 219, 220, 221, 222, 223, 224, 225, 228, 239, 241, 242, 246)
        for ($row = 2; $row -le $lastRow; $row++) {
            $qCell = $worksheet.Range("Q$row")
            try {
                $qFormula = [string]$qCell.Formula2
                if ($qFormula -match 'Exchange rate - base USD' -or $restoreQRows -contains $row) {
                    if ($row -eq 241) {
                        # Direct EUR/USD trade: received EUR 299,966.80 for USD 345,223.99.
                        Set-Formula $qCell '=$F241/ABS($F242)'
                    }
                    elseif ($row -eq 242) {
                        Set-Formula $qCell '=1'
                    }
                    else {
                        Set-Formula $qCell (Get-HistoricalFxFormula $row 'Exchange rate - base USD' 'USD' 'E' 'A')
                    }
                }
            }
            finally {
                Release-Com $qCell
            }

            $uCell = $worksheet.Range("U$row")
            try {
                Set-Formula $uCell (Get-CurrentFxFormula $row 'Exchange rate - base USD' 'USD' 'E')
            }
            finally {
                Release-Com $uCell
            }

            $derived = @{
                R = '=IF(NOT(ISNUMBER($F' + $row + ')),"",$F' + $row + '/$Q' + $row + ')'
                S = '=IF($D' + $row + '="","",SUMIF($D$2:$D' + $row + ',$D' + $row + ',$R$2:$R' + $row + '))'
                T = '=IF(NOT(ISNUMBER($F' + $row + ')),"",SUM($R$2:$R' + $row + '))'
                V = '=IF(NOT(ISNUMBER($F' + $row + ')),"",$F' + $row + '/$U' + $row + ')'
                W = '=IF($D' + $row + '="","",SUMIF($D$2:$D' + $row + ',$D' + $row + ',$V$2:$V' + $row + '))'
                X = '=IF(NOT(ISNUMBER($F' + $row + ')),"",SUM($V$2:$V' + $row + '))'
            }
            foreach ($column in @('R', 'S', 'T', 'V', 'W', 'X')) {
                $cell = $worksheet.Range("$column$row")
                try {
                    Set-Formula $cell $derived[$column]
                }
                finally {
                    Release-Com $cell
                }
            }
        }

        # The later-added SGD reporting block begins at row 211. Rebuild the
        # entire derived block because several of these rows were pasted values.
        for ($row = 211; $row -le $lastRow; $row++) {
            $zCell = $worksheet.Range("Z$row")
            $adCell = $worksheet.Range("AD$row")
            try {
                Set-Formula $zCell (Get-HistoricalFxFormula $row 'Exchange rate - base SGD' 'SGD' 'E' 'A')
                Set-Formula $adCell (Get-CurrentFxFormula $row 'Exchange rate - base SGD' 'SGD' 'E')
            }
            finally {
                Release-Com $zCell
                Release-Com $adCell
            }
            $derived = @{
                AA = '=IF(NOT(ISNUMBER($F' + $row + ')),"",$F' + $row + '/$Z' + $row + ')'
                AB = '=IF($D' + $row + '="","",SUMIF($D$2:$D' + $row + ',$D' + $row + ',$AA$2:$AA' + $row + '))'
                AC = '=IF(NOT(ISNUMBER($F' + $row + ')),"",SUM($AA$2:$AA' + $row + '))'
                AE = '=IF(NOT(ISNUMBER($F' + $row + ')),"",$F' + $row + '/$AD' + $row + ')'
                AF = '=IF($D' + $row + '="","",SUMIF($D$2:$D' + $row + ',$D' + $row + ',$AE$2:$AE' + $row + '))'
                AG = '=IF(NOT(ISNUMBER($F' + $row + ')),"",SUM($AE$2:$AE' + $row + '))'
            }
            foreach ($column in @('AA', 'AB', 'AC', 'AE', 'AF', 'AG')) {
                $cell = $worksheet.Range("$column$row")
                try {
                    Set-Formula $cell $derived[$column]
                }
                finally {
                    Release-Com $cell
                }
            }
        }

        # Restore the bond purchase cash amount from its own transaction inputs.
        $sourceFormulaCell = $worksheet.Range('F226')
        $targetFormulaCell = $worksheet.Range('F223')
        try {
            $targetFormulaCell.FormulaR1C1 = $sourceFormulaCell.FormulaR1C1
        }
        finally {
            Release-Com $sourceFormulaCell
            Release-Com $targetFormulaCell
        }

        # Normalize Bloomberg/security identifiers that had leading/trailing spaces.
        foreach ($address in @('G87', 'G88', 'G92', 'G122', 'G174', 'G216')) {
            $cell = $worksheet.Range($address)
            try {
                if ($cell.Value2 -is [string]) {
                    $cell.Value2 = ([string]$cell.Value2).Trim()
                }
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

function Repair-BondTransactions($workbook) {
    $worksheet = $workbook.Worksheets.Item('Bond Transactions')
    try {
        $lastCell = $worksheet.Cells.Item($worksheet.Rows.Count, 1).End(-4162)
        try {
            $lastRow = [int]$lastCell.Row
        }
        finally {
            Release-Com $lastCell
        }
        if ($lastRow -lt 156) {
            throw "Unexpected Bond Transactions last populated row: $lastRow"
        }

        for ($row = 9; $row -le $lastRow; $row++) {
            foreach ($column in @('T', 'AB')) {
                $cell = $worksheet.Range("$column$row")
                try {
                    if ($cell.HasFormula) {
                        Set-Formula $cell (Get-HistoricalFxFormula $row 'Exchange rate - base USD' 'USD' 'S' 'A')
                    }
                }
                finally {
                    Release-Com $cell
                }
            }

            $acCell = $worksheet.Range("AC$row")
            $beCell = $worksheet.Range("BE$row")
            try {
                Set-Formula $acCell (Get-CurrentFxFormula $row 'Exchange rate - base USD' 'USD' 'S')
                Set-Formula $beCell (Get-CurrentFxFormula $row 'Exchange rate - base SGD' 'SGD' 'S')
            }
            finally {
                Release-Com $acCell
                Release-Com $beCell
            }

            foreach ($column in @('BD', 'CF')) {
                $cell = $worksheet.Range("$column$row")
                try {
                    if ($cell.HasFormula) {
                        Set-Formula $cell (Get-HistoricalFxFormula $row 'Exchange rate - base SGD' 'SGD' 'S' 'A')
                    }
                }
                finally {
                    Release-Com $cell
                }
            }

            $cgCell = $worksheet.Range("CG$row")
            try {
                if ($cgCell.HasFormula) {
                    $formula = '=IF(OR($A' + $row + '="",NOT(ISNUMBER($CF' + $row + '))),NA(),LET(' +
                        'd,''Exchange rate - base SGD''!$A$8:$A$735,' +
                        'r,''Exchange rate - base SGD''!$B$8:$B$735,' +
                        'ok,(d<=$A' + $row + ')*ISNUMBER(r),' +
                        'ld,LOOKUP(2,1/ok,d),' +
                        'lr,LOOKUP(2,1/ok,r),' +
                        'IF($A' + $row + '-ld<=10,$CF' + $row + '/lr,NA())))'
                    Set-Formula $cgCell $formula
                }
            }
            finally {
                Release-Com $cgCell
            }
        }

        foreach ($address in @('D74', 'D75', 'D77', 'D95')) {
            $cell = $worksheet.Range($address)
            try {
                if ($cell.Value2 -is [string]) {
                    $cell.Value2 = ([string]$cell.Value2).Trim()
                }
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

function Repair-EquityTransactions($workbook) {
    $worksheet = $workbook.Worksheets.Item('Equity Transactions')
    try {
        foreach ($mapping in @(
            @('G11', "='Transactions List'!I111"),
            @('G12', "='Transactions List'!I127"),
            @('G14', "='Transactions List'!I129"),
            @('G17', "='Transactions List'!I174"),
            @('G18', "='Transactions List'!I175"),
            @('A19', "='Transactions List'!A184"),
            @('I19', "='Transactions List'!L184+'Transactions List'!M184")
        )) {
            $cell = $worksheet.Range($mapping[0])
            try {
                Set-Formula $cell $mapping[1]
            }
            finally {
                Release-Com $cell
            }
        }
    }
    finally {
        Release-Com $worksheet
    }

    $transactions = $workbook.Worksheets.Item('Transactions List')
    try {
        $ticker = $transactions.Range('G111')
        try {
            $ticker.Value2 = 'C6L SP Equity'
        }
        finally {
            Release-Com $ticker
        }
    }
    finally {
        Release-Com $transactions
    }
}

function Repair-StructuralFormulas($workbook) {
    $timeline = $workbook.Worksheets.Item('Bonds maturity and cpn timeline')
    try {
        $range = $timeline.Range('X9', 'X100')
        try {
            $range.FormulaR1C1 = '=IF(RC21="","",SUMIFS(R1C6:R1000C6,R1C1:R1000C1,">="&DATE(YEAR(RC21),MONTH(RC21),1),R1C1:R1000C1,"<="&EOMONTH(RC21,0)))'
        }
        finally {
            Release-Com $range
        }
    }
    finally {
        Release-Com $timeline
    }

    $goldPrices = $workbook.Worksheets.Item('Gold prices')
    try {
        $tickerCell = $goldPrices.Range('D4')
        try {
            Set-Formula $tickerCell '=IFERROR(TRANSPOSE(UNIQUE(FILTER(''Gold Transactions''!$D$9:$D$5000,(''Gold Transactions''!$D$9:$D$5000<>"")*(''Gold Transactions''!$D$9:$D$5000<>"-"),""))),"")'
        }
        finally {
            Release-Com $tickerCell
        }
    }
    finally {
        Release-Com $goldPrices
    }

    $cashAnalysis = $workbook.Worksheets.Item('Cash Transactions - analysis')
    try {
        $fxCell = $cashAnalysis.Range('J64')
        try {
            Set-Formula $fxCell '=IF(OR(D60="",D60="-"),"",BDP("EUR"&D60&" CURNCY","PX_LAST"))'
        }
        finally {
            Release-Com $fxCell
        }
    }
    finally {
        Release-Com $cashAnalysis
    }

    $pnl = $workbook.Worksheets.Item('BS P&L')
    try {
        $dividendCell = $pnl.Range('G30')
        try {
            Set-Formula $dividendCell '=SUMIF(''Transactions List''!C:C,"Dividend received",''Transactions List''!R:R)'
        }
        finally {
            Release-Com $dividendCell
        }
    }
    finally {
        Release-Com $pnl
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
        $worksheet = $workbook.Worksheets.Item($spec[0])
        $cell = $null
        try {
            $cell = $worksheet.Range($spec[1])
            $text = [string]$cell.Text
            $parts.Add(($spec[0] + '!' + $spec[1] + '=' + $text))
        }
        finally {
            Release-Com $cell
            Release-Com $worksheet
        }
    }
    return [string]::Join('|', $parts)
}

function Has-TransientBloombergValues($workbook) {
    $markers = @('Requesting Data', 'Retrieving Data', '#BUSY!', '#GETTING_DATA', '#CONNECT!')
    foreach ($sheetName in @(
        'Bond prices',
        'Equity prices',
        'Gold prices',
        'Exchange rate - base SGD',
        'Exchange rate - base USD',
        'Current Equity Positions',
        'Equity Analysis'
    )) {
        $worksheet = $workbook.Worksheets.Item($sheetName)
        $used = $null
        try {
            $used = $worksheet.UsedRange
            foreach ($marker in $markers) {
                $found = $null
                try {
                    $found = $used.Find($marker, [Type]::Missing, -4163, 2, 1, 1, $false, $false, $false)
                    if ($null -ne $found) {
                        return $true
                    }
                }
                catch {
                    # A failed Find is not evidence that Bloomberg is still busy.
                }
                finally {
                    Release-Com $found
                }
            }
        }
        finally {
            Release-Com $used
            Release-Com $worksheet
        }
    }
    return $false
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
        $worksheet = $workbook.Worksheets.Item($spec[0])
        $cell = $null
        try {
            $cell = $worksheet.Range($spec[1])
            $text = [string]$cell.Text
            $value = $cell.Value2
            if ($text.StartsWith('#') -or $text -match 'Requesting|Retrieving|BUSY|GETTING_DATA|CONNECT') {
                throw "Critical cell is not numeric: $($spec[0])!$($spec[1]) = $text"
            }
            if (-not ($value -is [byte] -or $value -is [int16] -or $value -is [int32] -or $value -is [int64] -or $value -is [single] -or $value -is [double] -or $value -is [decimal])) {
                throw "Critical cell is not numeric: $($spec[0])!$($spec[1]) = $text"
            }
        }
        finally {
            Release-Com $cell
            Release-Com $worksheet
        }
    }
}

if (Test-Path -LiteralPath $LogPath) {
    Remove-Item -LiteralPath $LogPath -Force
}
Write-Status 'starting'
Write-Log "Starting repair: $resolvedWorkbook"

$excel = $null
$workbooks = $null
$workbook = $null
$dummyWorkbook = $null
$ownsExcel = $false
$completed = $false
$excelPid = 0

try {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class WolfExcelPid {
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
'@
    $existingExcelPids = @(Get-Process -Name EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $excel = New-Object -ComObject Excel.Application
    [uint32]$newPid = 0
    [void][WolfExcelPid]::GetWindowThreadProcessId([IntPtr]$excel.Hwnd, [ref]$newPid)
    $excelPid = [int]$newPid
    if ($existingExcelPids -contains $excelPid) {
        throw "Excel COM reused an existing Excel process ($excelPid); refusing to continue"
    }
    $ownsExcel = $true
    Write-Log "Created isolated Excel process PID=$excelPid"

    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AskToUpdateLinks = $false
    $excel.EnableEvents = $false
    $excel.ScreenUpdating = $false
    $excel.AutomationSecurity = 3

    $workbooks = $excel.Workbooks
    $dummyWorkbook = $workbooks.Add()
    $excel.Calculation = -4135 # xlCalculationManual

    $workbook = $workbooks.Open($resolvedWorkbook, 0, $false)
    if ([IO.Path]::GetFullPath([string]$workbook.FullName) -ne $resolvedWorkbook) {
        throw "Excel opened the wrong workbook: $($workbook.FullName)"
    }
    $dummyWorkbook.Close($false)
    Release-Com $dummyWorkbook
    $dummyWorkbook = $null

    $bloombergAddin = $null
    try {
        $bloombergAddin = $excel.COMAddIns.Item('Bofaddin.Connect')
        if (-not $bloombergAddin.Connect) {
            throw 'Bloomberg COM add-in is not connected in the isolated Excel instance'
        }
    }
    finally {
        Release-Com $bloombergAddin
    }
    Write-Status 'repairing'

    $externalReplacementCount = Remove-ExternalFormulaReferences $workbook
    Write-Log "Rewrote external-link formula cells: $externalReplacementCount"

    Extend-FxSheet $workbook 'Exchange rate - base SGD' 556
    Extend-FxSheet $workbook 'Exchange rate - base USD' 598

    # Fill the genuine historical gap in USD/AUD only; preserve all other raw observations.
    $usdFx = $workbook.Worksheets.Item('Exchange rate - base USD')
    try {
        $audGap = $usdFx.Range('K8', 'K30')
        try {
            $audGap.FormulaR1C1 = '=IF(OR(RC1="",R5C="",R5C="-"),"",BDH(R5C,"PX_LAST",RC1,RC1))'
        }
        finally {
            Release-Com $audGap
        }
    }
    finally {
        Release-Com $usdFx
    }

    Repair-TransactionsList $workbook
    Repair-BondTransactions $workbook
    Repair-EquityTransactions $workbook
    Repair-StructuralFormulas $workbook

    $guardCount = Guard-BloombergFormulas $workbook @(
        'Bond prices',
        'Equity prices',
        'Gold prices',
        'Current Equity Positions',
        'Exited Equity Positions',
        'Equity Analysis'
    )
    Write-Log "Guarded Bloomberg formula cells: $guardCount"

    $remainingExternalFormulaCount = Count-ExternalFormulaReferences $workbook
    if ($remainingExternalFormulaCount -ne 0) {
        throw "External workbook references remain in $remainingExternalFormulaCount formula cells"
    }

    # Once every formula is internal, removing cached link objects cannot value-out a live formula.
    $links = $workbook.LinkSources(1)
    if ($null -ne $links) {
        foreach ($link in @($links)) {
            Write-Log "Removing orphaned external link cache: $link"
            $workbook.BreakLink([string]$link, 1)
        }
    }
    $remainingLinks = $workbook.LinkSources(1)
    if ($null -ne $remainingLinks) {
        throw 'Workbook still reports external Excel links after formula repair'
    }

    $workbook.CheckCompatibility = $false
    $workbook.ForceFullCalculation = $true
    try {
        $workbook.FullCalculationOnLoad = $true
    }
    catch {
        Write-Log "FullCalculationOnLoad is unavailable in this Excel COM build; ForceFullCalculation remains enabled"
    }
    $workbook.Save()
    Write-Log 'Saved structural-repair checkpoint'

    Write-Status 'calculating'
    $excel.Calculation = -4105 # xlCalculationAutomatic
    $excel.CalculateFullRebuild()
    try {
        $excel.CalculateUntilAsyncQueriesDone()
    }
    catch {
        Write-Log "CalculateUntilAsyncQueriesDone returned: $($_.Exception.Message)"
    }

    $deadline = (Get-Date).AddMinutes(12)
    $lastSnapshot = ''
    $stableCount = 0
    $pollCount = 0
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5
        $pollCount++
        $snapshot = Get-KeySnapshot $workbook
        $calculationDone = ([int]$excel.CalculationState -eq 0)
        $ready = [bool]$excel.Ready
        if ($calculationDone -and $ready -and $snapshot -eq $lastSnapshot) {
            $stableCount++
        }
        else {
            $stableCount = 0
        }
        $lastSnapshot = $snapshot
        if (($pollCount % 6) -eq 0) {
            Write-Log "Calculation poll $pollCount stable=$stableCount state=$($excel.CalculationState) ready=$ready $snapshot"
        }
        if ($stableCount -ge 3) {
            if (-not (Has-TransientBloombergValues $workbook)) {
                break
            }
            $stableCount = 0
            Write-Log 'Critical cells were stable, but Bloomberg transient values remain'
        }
    }
    if ($stableCount -lt 3) {
        throw "Bloomberg/Excel calculation did not stabilize before the 12-minute deadline. Last snapshot: $lastSnapshot"
    }

    Assert-CriticalCells $workbook
    Write-Log "Critical cells validated: $lastSnapshot"
    $workbook.Save()
    Write-Log 'Saved recalculated repaired workbook'
    Write-Status 'complete'
    $completed = $true
}
catch {
    Write-Log ('FAILED: ' + $_.Exception.Message)
    Write-Log $_.ScriptStackTrace
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
            try { $excel.Quit() } catch {}
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
            Write-Log "WARNING: owned Excel process PID=$excelPid is still running after Quit"
        }
    }
    if (-not $completed -and (Get-Content -LiteralPath $StatusPath -ErrorAction SilentlyContinue) -eq 'calculating') {
        Write-Status 'failed: repair process ended before completion'
    }
}
