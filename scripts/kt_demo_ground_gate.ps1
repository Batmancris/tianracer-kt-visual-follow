param(
    [string]$RobotIp = "10.217.185.241",
    [string]$HoverGateEvidence,
    [ValidateRange(1, 240)]
    [int]$MaxHoverGateAgeMinutes = 30
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

function Get-LatestRawHoverEvidence {
    $items = Get-ChildItem (Join-Path $PSScriptRoot "..\reports\artifacts\kt-demo-hover-*.txt") -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike 'kt-demo-hover-gate-*' }

    return $items |
        Sort-Object LastWriteTime, Name -Descending |
        Select-Object -First 1
}

if (-not $HoverGateEvidence) {
    $latestPassingHoverGate = Get-ChildItem (Join-Path $PSScriptRoot "..\reports\artifacts\kt-demo-hover-gate-*.txt") -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        Where-Object { (Get-Content -LiteralPath $_.FullName -Raw) -match 'Hover gate PASSED' } |
        Select-Object -First 1

    if (-not $latestPassingHoverGate) {
        throw "No passing hover-gate artifact found. Run kt_demo_hover_gate.ps1 on a valid hover evidence file before ground gate."
    }

    $HoverGateEvidence = $latestPassingHoverGate.FullName
}

$resolvedHoverGate = Resolve-Path -LiteralPath $HoverGateEvidence
$hoverGateItem = Get-Item -LiteralPath $resolvedHoverGate
$hoverGateText = Get-Content -LiteralPath $resolvedHoverGate -Raw
$hoverEvidenceMatch = [regex]::Match($hoverGateText, '^Hover evidence:\s+(.+)$', [System.Text.RegularExpressions.RegexOptions]::Multiline)

if (-not $hoverEvidenceMatch.Success) {
    throw "Hover gate artifact is missing its source hover evidence path: $resolvedHoverGate"
}

$hoverEvidencePath = $hoverEvidenceMatch.Groups[1].Value.Trim()
if (-not (Test-Path -LiteralPath $hoverEvidencePath)) {
    throw "Hover gate source hover evidence path does not exist: $hoverEvidencePath"
}

$resolvedHoverEvidence = Resolve-Path -LiteralPath $hoverEvidencePath
$latestRawHover = Get-LatestRawHoverEvidence
if (-not $latestRawHover) {
    throw "No raw hover evidence file found under reports/artifacts/kt-demo-hover-*.txt"
}

$resolvedLatestRawHover = Resolve-Path -LiteralPath $latestRawHover.FullName

if ($hoverGateText -notmatch 'Hover gate PASSED') {
    throw "Hover gate artifact does not pass: $resolvedHoverGate"
}

if ($resolvedHoverEvidence.Path -ne $resolvedLatestRawHover.Path) {
    throw "Hover gate artifact is not based on the latest raw hover evidence. Latest raw hover: $resolvedLatestRawHover ; hover gate uses: $resolvedHoverEvidence"
}

$hoverGateAgeMinutes = ((Get-Date) - $hoverGateItem.LastWriteTime).TotalMinutes
if ($hoverGateAgeMinutes -gt $MaxHoverGateAgeMinutes) {
    throw ("Hover gate artifact is stale ({0:N1} min old, limit {1} min): {2}" -f $hoverGateAgeMinutes, $MaxHoverGateAgeMinutes, $resolvedHoverGate)
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = Join-Path $PSScriptRoot "..\reports\artifacts\kt-demo-ground-gate-$timestamp.txt"
$outDir = Split-Path -Parent $outFile
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$remote = @"
echo '--- core ---' &&
ros2 node list | grep -E '^/tianracer_core$|^/tianbot_core$' || true &&
echo '--- ackermann ---' &&
ros2 topic info /ackermann_cmd -v || true &&
echo '--- scan_raw hz ---' &&
timeout 7 stdbuf -oL ros2 topic hz /tianracer/scan_raw 2>/dev/null || true &&
echo '--- scan hz ---' &&
timeout 7 stdbuf -oL ros2 topic hz /tianracer/scan 2>/dev/null || true &&
echo '--- targets hz ---' &&
timeout 7 stdbuf -oL ros2 topic hz /bear_detection/targets 2>/dev/null || true &&
echo '--- forbidden ---' &&
ros2 node list | grep -E 'joy|teleop|navigation|nav2|smooth_follow|kt_visual_lidar_follow' || true
"@

Write-Host "KT Demo Ground Gate  sunrise@$RobotIp" -ForegroundColor Cyan
$result = Invoke-KtRobotBash -RobotIp $RobotIp -RemoteBody $remote
$result | Tee-Object -FilePath $outFile

$text = ($result | Out-String)
$errors = @()
$report = [System.Collections.Generic.List[string]]::new()

if ($text -notmatch '/tianracer_core' -and $text -notmatch '/tianbot_core') {
    $errors += "missing tianracer_core/tianbot_core node"
}
if ($text -notmatch 'Subscription count:\s+1' -or $text -notmatch 'Node name:\s+tianracer_core') {
    $errors += "ackermann subscriber is not cleanly owned by tianracer_core"
}
if ($text -notmatch 'average rate:\s+9\.' -and $text -notmatch 'average rate:\s+10\.') {
    $errors += "scan topics are not reporting near-10Hz rates"
}
if ($text -notmatch 'targets hz' -or $text -notmatch 'average rate:\s+[1-9]') {
    $errors += "bear_detection targets rate is missing"
}
if ($text -match 'joy|teleop|navigation|nav2|smooth_follow|kt_visual_lidar_follow') {
    $errors += "forbidden nodes detected"
}

$report.Add("")
$report.Add("Ground gate hover-gate evidence: $resolvedHoverGate")
$report.Add("Ground gate raw hover evidence: $resolvedHoverEvidence")
$report.Add("Ground gate latest raw hover evidence: $resolvedLatestRawHover")
$report.Add(("Ground gate hover-gate age minutes: {0:N1}" -f $hoverGateAgeMinutes))

if ($errors.Count -gt 0) {
    $report.Add("Ground gate FAILED")
    foreach ($errorText in $errors) {
        $report.Add("- $errorText")
    }
    Add-Content -Path $outFile -Value $report.ToArray()
    Write-Error ("Ground gate FAILED: " + ($errors -join "; "))
}

$report.Add("Ground gate PASSED")
Add-Content -Path $outFile -Value $report.ToArray()
Write-Host "Saved ground-gate evidence to $outFile" -ForegroundColor Green
Write-Host "Hover-gate evidence: $resolvedHoverGate" -ForegroundColor Green
Write-Host ("Hover-gate age minutes: {0:N1}" -f $hoverGateAgeMinutes) -ForegroundColor Green
Write-Host "Ground gate PASSED" -ForegroundColor Green
