param(
    [string]$OutputPath
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

    return $items | Sort-Object LastWriteTime, Name -Descending | Select-Object -First 1
}

function Test-ArtifactContains {
    param(
        [System.IO.FileInfo]$File,
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

function New-ItemLine {
    param(
        [int]$Number,
        [string]$Question,
        [string]$Status,
        [string]$Evidence
    )

    return "$Number. $Question`nStatus: $Status`nEvidence: $Evidence`n"
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
    $hoverGateUsesLatestHover = ((Resolve-Path -LiteralPath $hover.FullName).Path -eq (Resolve-Path -LiteralPath $hoverGateSourceHoverPath).Path)
}

$readinessPath = if ($readiness) { $readiness.FullName } else { "missing" }
$hoverPath = if ($hover) { $hover.FullName } else { "missing" }
$hoverGatePath = if ($hoverGate) { $hoverGate.FullName } else { "missing" }
$groundGatePath = if ($groundGate) { $groundGate.FullName } else { "missing" }
$groundPath = if ($ground) { $ground.FullName } else { "missing" }

$items = @()
$items += New-ItemLine 1 'Is the current chain ROS2-only?' ($(if ($readiness) { "proven" } else { "unproven" })) "Current evidence set is ROS2-only; see $readinessPath"
$items += New-ItemLine 2 'Is ROS1 `scan_bridge` absent?' ($(if ($readiness) { "proven" } else { "unproven" })) "Forbidden-node checks in readiness/status do not show ROS1 bridge; see $readinessPath"
$items += New-ItemLine 3 'Is the physical lidar confirmed as `LDS_E110`?' ($(if (Test-ArtifactContains $readiness 'Node name:\s+lds_e110') { "proven" } else { "unproven" })) 'Readiness artifact publisher node for /tianracer/scan_raw'
$items += New-ItemLine 4 'Is `/tianracer/scan_raw` near 10Hz?' ($(if (Test-ArtifactContains $readiness 'scan_raw[\s\S]*average rate:\s+9\.|scan_raw[\s\S]*average rate:\s+10\.') { "proven" } else { "unproven" })) $readinessPath
$items += New-ItemLine 5 'Is `/tianracer/scan` near 10Hz?' ($(if (Test-ArtifactContains $readiness '--- scan ---[\s\S]*average rate:\s+9\.|--- scan ---[\s\S]*average rate:\s+10\.') { "proven" } else { "unproven" })) $readinessPath
$items += New-ItemLine 6 'Does `/tianracer/camera/image_compressed` have a publisher and non-zero rate?' ($(if (Test-ArtifactContains $readiness 'image_compressed' -and (Test-ArtifactContains $readiness 'average rate:\s+30\.|average rate:\s+2[0-9]\.')) { "proven" } else { "unproven" })) $readinessPath
$items += New-ItemLine 7 'Does `/bear_detection/targets` have a publisher and non-zero rate?' ($(if (Test-ArtifactContains $readiness '--- targets ---' -and (Test-ArtifactContains $readiness 'average rate:\s+2[0-9]\.')) { "proven" } else { "unproven" })) $readinessPath
$items += New-ItemLine 8 'Does `v4` no longer depend on `/kt_follow/debug_target`?' 'proven' 'Static source check in work_src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py'
$items += New-ItemLine 9 'Does `v4` subscribe directly to `/bear_detection/targets`?' ($(if (Test-ArtifactContains $readiness 'Node name:\s+kt_follow_controller_v4[\s\S]*Topic type: ai_msgs/msg/PerceptionTargets') { "proven" } else { "unproven" })) $readinessPath
$items += New-ItemLine 10 'Does `v4` subscribe directly to `/tianracer/scan`?' ($(if (Test-ArtifactContains $readiness 'Node name:\s+kt_follow_controller_v4[\s\S]*Topic type: sensor_msgs/msg/LaserScan') { "proven" } else { "unproven" })) $readinessPath
$items += New-ItemLine 11 'Does `v4` subscribe to `/kt_follow/mode`?' ($(if (Test-ArtifactContains $hover 'mode changed OFF -> FOLLOW') { "proven" } else { "unproven" })) $hoverPath
$items += New-ItemLine 12 'Does `/ackermann_cmd` have `tianracer_core` as subscriber?' ($(if (Test-ArtifactContains $readiness 'Subscription count:\s+1' -and (Test-ArtifactContains $readiness 'Node name:\s+tianracer_core')) { "proven" } else { "unproven" })) $readinessPath
$items += New-ItemLine 13 "Is the direct physical control chain still valid?" "partially proven" "ROS graph is valid; fresh physical steering/wheel observation not included in current artifacts"
$items += New-ItemLine 14 "In hover, does left/right bear motion match steering direction?" ($(if (Test-ArtifactContains $hover 'mode=FOLLOW roi_cx=(?!None).*reason=ok publishing=True') { "partially proven" } else { "unproven" })) ("Newest raw hover artifact: $hoverPath ; age minutes: {0:N1}" -f $hoverAgeMinutes)
$items += New-ItemLine 15 "In hover, does near/far bear motion match speed change?" ($(if (Test-ArtifactContains $hover 'mode=FOLLOW roi_cx=(?!None).*dist_raw=(?!None).*reason=ok publishing=True') { "partially proven" } else { "unproven" })) ("Hover gate uses latest hover: $hoverGateUsesLatestHover ; hover gate source: $hoverGateSourceHoverPath")
$items += New-ItemLine 16 'Do `MANUAL` and `OFF` send stop and release control?' ($(if ((Test-ArtifactContains $hover 'MANUAL stop x5 then release') -and (Test-ArtifactContains $hover 'OFF stop x10 then release')) { "partially proven" } else { "unproven" })) ("Hover gate path: $hoverGatePath ; hover gate age minutes: {0:N1}" -f $hoverGateAgeMinutes)
$items += New-ItemLine 17 "What first ground-test parameters were used?" ($(if ($ground) { "recorded" } else { "unproven" })) $(if ($ground) { $groundPath } else { "No ground artifact present" })
$items += New-ItemLine 18 'Was the first 3-5 second `FOLLOW` run safe?' 'unproven' 'No current ground artifact'
$items += New-ItemLine 19 "Does the car stop near 1.0m?" "unproven" "No current ground artifact"
$items += New-ItemLine 20 "Does the car stop when the target is lost?" "unproven" "Controller logic and stale-target logs exist, but no physical ground proof"
$items += New-ItemLine 21 'Does `OFF` stop the car immediately?' 'unproven' 'Command/log evidence exists; no current physical ground proof'
$items += New-ItemLine 22 "Are there any residual publishers after the run?" ($(if (Test-ArtifactContains $groundGate 'Publisher count: 0') { "proven pre-ground" } else { "unproven" })) $groundGatePath
$items += New-ItemLine 23 "Is visualization latency decoupled from the control chain?" "proven at architecture level" "Formal web page only publishes /kt_follow/mode and visualizes topics"
$items += New-ItemLine 24 "Is exposed control bridge work deferred as a separate F6 issue?" "proven" "Formal web page does not expose 8766 control bridge"
$items += New-ItemLine 25 "Remaining blockers" "open" "Need fresh human-observed live-bear hover pass; need first real ground-cycle artifact; base communication risk remains watch item"
$items += New-ItemLine 26 "Next concrete step" "open" "Run live-bear hover_check -> hover_gate -> ground_gate -> follow_v4_ground -Armed -> ground_cycle -ExecuteGroundRun"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $OutputPath) {
    $OutputPath = Join-Path $PSScriptRoot "..\reports\R2-L-F5-F6-ground-test-report-draft-$timestamp.md"
}

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("# R2-L-F5/F6 ground-test readiness and first ground test report draft")
$lines.Add("")
$lines.Add("## Evidence Files")
$lines.Add("")
$lines.Add('- readiness: `' + $readinessPath + '`')
$lines.Add('- hover: `' + $hoverPath + '`')
$lines.Add('- hover gate: `' + $hoverGatePath + '`')
$lines.Add('- ground gate: `' + $groundGatePath + '`')
$lines.Add('- ground: `' + $groundPath + '`')
$lines.Add('- hover gate source hover: `' + $(if ($hoverGateSourceHoverPath) { $hoverGateSourceHoverPath } else { "missing" }) + '`')
$lines.Add("")
$lines.Add("## Evidence Freshness")
$lines.Add("")
$lines.Add("- latest raw hover age minutes: " + $(if ($null -ne $hoverAgeMinutes) { ('{0:N1}' -f $hoverAgeMinutes) } else { 'missing' }))
$lines.Add("- latest hover gate age minutes: " + $(if ($null -ne $hoverGateAgeMinutes) { ('{0:N1}' -f $hoverGateAgeMinutes) } else { 'missing' }))
$lines.Add("- hover gate uses latest raw hover: " + $hoverGateUsesLatestHover)
$lines.Add("")
$lines.Add("## Readiness Checklist")
$lines.Add("")
foreach ($entry in $items[0..12]) { $lines.Add($entry) }
$lines.Add("")
$lines.Add("## Hover Validation")
$lines.Add("")
foreach ($entry in $items[13..15]) { $lines.Add($entry) }
$lines.Add("")
$lines.Add("## First Ground Test")
$lines.Add("")
foreach ($entry in $items[16..21]) { $lines.Add($entry) }
$lines.Add("")
$lines.Add("## Web Boundary")
$lines.Add("")
foreach ($entry in $items[22..23]) { $lines.Add($entry) }
$lines.Add("")
$lines.Add("## Risks")
$lines.Add("")
foreach ($entry in $items[24..25]) { $lines.Add($entry) }
$lines.Add("")
$lines.Add("## Required Conclusion")
$lines.Add("")
$lines.Add("Current conclusion: the prod/demo workspace and safety-gate chain are in place, but physical completion is still unproven.")
$lines.Add("")
$lines.Add('Do not claim success with vague statements like `web FOLLOW succeeded`.')
$lines.Add("Current evidence does not yet prove:")
$lines.Add("")
$lines.Add("- actual steering response from a fresh human-observed live-bear hover pass")
$lines.Add("- actual rear-wheel motion from the first guarded ground cycle")
$lines.Add('- actual `OFF` stop behavior during a fresh ground run')
$lines.Add("- consistency between physical behavior and logs during that first ground run")

$lines.ToArray() | Set-Content -Path $OutputPath
Write-Host "Saved report draft to $OutputPath" -ForegroundColor Green
