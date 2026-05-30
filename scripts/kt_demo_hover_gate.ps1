param(
    [string]$EvidenceFile,
    [ValidateRange(1, 240)]
    [int]$MaxEvidenceAgeMinutes = 30
)

$ErrorActionPreference = "Stop"

function Get-LatestRawHoverEvidence {
    $items = Get-ChildItem (Join-Path $PSScriptRoot "..\reports\artifacts\kt-demo-hover-*.txt") -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike 'kt-demo-hover-gate-*' }

    return $items |
        Sort-Object LastWriteTime, Name -Descending |
        Select-Object -First 1
}

if (-not $EvidenceFile) {
    $latest = Get-LatestRawHoverEvidence

    if (-not $latest) {
        throw "No hover evidence file found under reports/artifacts/kt-demo-hover-*.txt"
    }

    $EvidenceFile = $latest.FullName
}

$resolvedEvidence = Resolve-Path -LiteralPath $EvidenceFile
$evidenceItem = Get-Item -LiteralPath $resolvedEvidence
$text = Get-Content -LiteralPath $resolvedEvidence -Raw

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$outFile = Join-Path $PSScriptRoot "..\reports\artifacts\kt-demo-hover-gate-$timestamp.txt"
$outDir = Split-Path -Parent $outFile
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$errors = @()
$warnings = @()

if ($text -notmatch 'mode changed OFF -> FOLLOW') {
    $errors += "missing OFF -> FOLLOW transition"
}
if ($text -notmatch 'mode=FOLLOW roi_cx=(?!None).*dist_raw=(?!None).*valid_scan_pts=([1-9][0-9]*) .*reason=ok publishing=True') {
    $errors += "missing live FOLLOW sample with roi/dist/scan and reason=ok"
}
if ($text -notmatch 'MANUAL stop x5 then release') {
    $errors += "missing MANUAL stop release sequence"
}
if ($text -notmatch 'OFF stop x10 then release') {
    $errors += "missing OFF stop release sequence"
}
if ($text -match "ignoring invalid mode 'False'") {
    $warnings += "artifact still contains legacy invalid OFF publication ('False'); this is tolerated for historical evidence but should not appear in fresh runs"
}

$report = [System.Collections.Generic.List[string]]::new()
$report.Add("Hover evidence: $resolvedEvidence")
$report.Add("Hover evidence last write: $($evidenceItem.LastWriteTime.ToString('s'))")
$report.Add("Hover gate generated at: $((Get-Date).ToString('s'))")
$report.Add("Hover gate max evidence age minutes: $MaxEvidenceAgeMinutes")
$report.Add("")

$evidenceAgeMinutes = ((Get-Date) - $evidenceItem.LastWriteTime).TotalMinutes
if ($evidenceAgeMinutes -gt $MaxEvidenceAgeMinutes) {
    $errors += ("hover evidence is stale ({0:N1} min old, limit {1} min)" -f $evidenceAgeMinutes, $MaxEvidenceAgeMinutes)
}

if ($errors.Count -gt 0) {
    $report.Add("Hover gate FAILED")
    $report.Add("")
    foreach ($errorText in $errors) {
        $report.Add("- $errorText")
    }
    if ($warnings.Count -gt 0) {
        $report.Add("")
        $report.Add("Warnings")
        foreach ($warningText in $warnings) {
            $report.Add("- $warningText")
        }
    }
    $report.ToArray() | Set-Content -Path $outFile
    Write-Host "Saved hover-gate evidence to $outFile" -ForegroundColor Yellow
    throw ("Hover gate FAILED: " + ($errors -join "; "))
}

$report.Add("Hover gate PASSED")
$report.Add("")
$report.Add("- OFF -> FOLLOW transition found")
$report.Add("- At least one live FOLLOW sample with roi/dist/scan and reason=ok found")
$report.Add("- MANUAL stop x5 release found")
$report.Add("- OFF stop x10 release found")
if ($warnings.Count -gt 0) {
    $report.Add("")
    $report.Add("Warnings")
    foreach ($warningText in $warnings) {
        $report.Add("- $warningText")
    }
}
$report.ToArray() | Set-Content -Path $outFile
Write-Host "Saved hover-gate evidence to $outFile" -ForegroundColor Green
Write-Host "Hover gate PASSED" -ForegroundColor Green
