param(
    [switch]$IncludeArtifactPaths,
    [ValidateRange(1, 240)]
    [int]$MaxHoverEvidenceAgeMinutes = 30,
    [ValidateRange(1, 240)]
    [int]$MaxHoverGateAgeMinutes = 30
)

$ErrorActionPreference = "Stop"

function Get-LatestArtifact {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Pattern,
        [string[]]$ExcludeNamePatterns = @()
    )

    $items = Get-ChildItem $Pattern -ErrorAction SilentlyContinue
    foreach ($excludePattern in $ExcludeNamePatterns) {
        $items = $items | Where-Object { $_.Name -notlike $excludePattern }
    }

    return $items |
        Sort-Object LastWriteTime, Name -Descending |
        Select-Object -First 1
}

function Test-ArtifactContains {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.FileInfo]$File,
        [Parameter(Mandatory = $true)]
        [string]$Pattern
    )

    if (-not $File) {
        return $false
    }

    return (Get-Content -LiteralPath $File.FullName -Raw) -match $Pattern
}

function Get-AgeMinutes {
    param(
        [System.IO.FileInfo]$File
    )

    if (-not $File) {
        return $null
    }

    return ((Get-Date) - $File.LastWriteTime).TotalMinutes
}

function Get-HoverGateSourceHoverPath {
    param(
        [System.IO.FileInfo]$File
    )

    if (-not $File) {
        return $null
    }

    $match = [regex]::Match((Get-Content -LiteralPath $File.FullName -Raw), '^Hover evidence:\s+(.+)$', [System.Text.RegularExpressions.RegexOptions]::Multiline)
    if (-not $match.Success) {
        return $null
    }

    return $match.Groups[1].Value.Trim()
}

$artifactRoot = Join-Path $PSScriptRoot "..\reports\artifacts"
$readiness = Get-LatestArtifact -Pattern (Join-Path $artifactRoot "kt-demo-readiness-*.txt")
$hover = Get-LatestArtifact -Pattern (Join-Path $artifactRoot "kt-demo-hover-*.txt") -ExcludeNamePatterns @("kt-demo-hover-gate-*")
$hoverGate = Get-LatestArtifact -Pattern (Join-Path $artifactRoot "kt-demo-hover-gate-*.txt")
$groundGate = Get-LatestArtifact -Pattern (Join-Path $artifactRoot "kt-demo-ground-gate-*.txt")
$ground = Get-LatestArtifact -Pattern (Join-Path $artifactRoot "kt-demo-ground-*.txt") -ExcludeNamePatterns @("kt-demo-ground-gate-*")
$hoverAgeMinutes = Get-AgeMinutes -File $hover
$hoverGateAgeMinutes = Get-AgeMinutes -File $hoverGate
$hoverGateSourceHoverPath = Get-HoverGateSourceHoverPath -File $hoverGate
$hoverGateSourceHoverExists = [bool]$hoverGateSourceHoverPath -and (Test-Path -LiteralPath $hoverGateSourceHoverPath)
$hoverGateUsesLatestHover = $false
if ($hover -and $hoverGateSourceHoverExists) {
    $resolvedLatestHover = (Resolve-Path -LiteralPath $hover.FullName).Path
    $resolvedGateHover = (Resolve-Path -LiteralPath $hoverGateSourceHoverPath).Path
    $hoverGateUsesLatestHover = ($resolvedLatestHover -eq $resolvedGateHover)
}
$hoverEvidenceFresh = ($null -ne $hoverAgeMinutes) -and ($hoverAgeMinutes -le $MaxHoverEvidenceAgeMinutes)
$hoverGateFresh = ($null -ne $hoverGateAgeMinutes) -and ($hoverGateAgeMinutes -le $MaxHoverGateAgeMinutes)

$status = [ordered]@{
    readiness_present = [bool]$readiness
    readiness_scan_ok = Test-ArtifactContains -File $readiness -Pattern 'average rate:\s+10\.|average rate:\s+9\.'
    readiness_targets_ok = ((Test-ArtifactContains -File $readiness -Pattern '--- targets ---') -and (Test-ArtifactContains -File $readiness -Pattern 'average rate:\s+2[0-9]\.|average rate:\s+[1-9]'))
    readiness_ackermann_subscriber_ok = ((Test-ArtifactContains -File $readiness -Pattern 'Subscription count:\s+1') -and (Test-ArtifactContains -File $readiness -Pattern 'Node name:\s+tianracer_core'))
    hover_present = [bool]$hover
    hover_age_minutes = if ($null -ne $hoverAgeMinutes) { [math]::Round($hoverAgeMinutes, 1) } else { $null }
    hover_fresh = $hoverEvidenceFresh
    hover_has_live_follow = Test-ArtifactContains -File $hover -Pattern 'mode=FOLLOW roi_cx=(?!None).*dist_raw=(?!None).*reason=ok publishing=True'
    hover_gate_present = [bool]$hoverGate
    hover_gate_pass = Test-ArtifactContains -File $hoverGate -Pattern 'Hover gate PASSED'
    hover_gate_age_minutes = if ($null -ne $hoverGateAgeMinutes) { [math]::Round($hoverGateAgeMinutes, 1) } else { $null }
    hover_gate_fresh = $hoverGateFresh
    hover_gate_source_hover_exists = $hoverGateSourceHoverExists
    hover_gate_uses_latest_hover = $hoverGateUsesLatestHover
    ground_gate_present = [bool]$groundGate
    ground_gate_pass = Test-ArtifactContains -File $groundGate -Pattern 'Ground gate PASSED'
    ground_present = [bool]$ground
}

$allGreenBeforeGround = $status.readiness_present -and
    $status.readiness_scan_ok -and
    $status.readiness_targets_ok -and
    $status.readiness_ackermann_subscriber_ok -and
    $status.hover_fresh -and
    $status.hover_has_live_follow -and
    $status.hover_gate_pass -and
    $status.hover_gate_fresh -and
    $status.hover_gate_uses_latest_hover -and
    $status.ground_gate_pass

Write-Host "KT Demo Summary" -ForegroundColor Cyan
Write-Host ("readiness: {0}" -f ($(if ($status.readiness_present) { "present" } else { "missing" })))
Write-Host ("readiness scan ok: {0}" -f $status.readiness_scan_ok)
Write-Host ("readiness targets ok: {0}" -f $status.readiness_targets_ok)
Write-Host ("ackermann subscriber ok: {0}" -f $status.readiness_ackermann_subscriber_ok)
Write-Host ("hover present: {0}" -f $status.hover_present)
Write-Host ("hover age minutes: {0}" -f $status.hover_age_minutes)
Write-Host ("hover fresh: {0}" -f $status.hover_fresh)
Write-Host ("hover has live FOLLOW: {0}" -f $status.hover_has_live_follow)
Write-Host ("hover gate pass: {0}" -f $status.hover_gate_pass)
Write-Host ("hover gate age minutes: {0}" -f $status.hover_gate_age_minutes)
Write-Host ("hover gate fresh: {0}" -f $status.hover_gate_fresh)
Write-Host ("hover gate source hover exists: {0}" -f $status.hover_gate_source_hover_exists)
Write-Host ("hover gate uses latest hover: {0}" -f $status.hover_gate_uses_latest_hover)
Write-Host ("ground gate pass: {0}" -f $status.ground_gate_pass)
Write-Host ("ground artifact present: {0}" -f $status.ground_present)
Write-Host ("pre-ground chain green: {0}" -f $allGreenBeforeGround)

if ($IncludeArtifactPaths) {
    Write-Host ""
    Write-Host "Artifacts" -ForegroundColor Cyan
    foreach ($pair in @(
        @{ Name = 'readiness'; File = $readiness },
        @{ Name = 'hover'; File = $hover },
        @{ Name = 'hover_gate'; File = $hoverGate },
        @{ Name = 'ground_gate'; File = $groundGate },
        @{ Name = 'ground'; File = $ground }
    )) {
        if ($pair.File) {
            Write-Host ("{0}: {1}" -f $pair.Name, $pair.File.FullName)
        } else {
            Write-Host ("{0}: missing" -f $pair.Name)
        }
    }
    Write-Host ("hover_gate_source_hover: {0}" -f $(if ($hoverGateSourceHoverPath) { $hoverGateSourceHoverPath } else { "missing" }))
}
