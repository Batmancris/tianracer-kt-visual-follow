Set-StrictMode -Version Latest

function Invoke-KtRobotBash {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RobotIp,
        [Parameter(Mandatory = $true)]
        [string]$RobotUser,
        [Parameter(Mandatory = $true)]
        [string]$RemoteBody
    )

    $preamble = @"
set -e
if [ -f ~/.bashrc ]; then
  source ~/.bashrc >/dev/null 2>&1 || true
fi
if command -v ros2_setup >/dev/null 2>&1; then
  ros2_setup >/dev/null 2>&1 || true
fi
if [ -f ~/tianracer_ros2_ws/install/setup.bash ]; then
  source ~/tianracer_ros2_ws/install/setup.bash >/dev/null 2>&1 || true
fi
$RemoteBody
"@

    $script = $preamble -replace "`r`n", "`n"
    return $script | ssh "$RobotUser@$RobotIp" "tr -d '\r' | bash -s"
}

function Get-KtReadySummary {
    param(
        [string[]]$Lines
    )

    $markers = @{}
    $blockers = New-Object System.Collections.Generic.List[string]

    foreach ($line in $Lines) {
        if ($null -eq $line) {
            continue
        }

        $text = $line.ToString().Trim()
        if ($text -match '^READY_CHECK\s+([A-Z0-9_]+)=(.*)$') {
            $markers[$matches[1]] = $matches[2].Trim()
            continue
        }

        if ($text -match '^READY_BLOCKER:\s*(.+)$') {
            [void]$blockers.Add($matches[1].Trim())
            continue
        }

        if ($text -match '^READY_TO_FOLLOW:\s*(YES|NO)$') {
            $markers["READY_TO_FOLLOW"] = $matches[1]
        }
    }

    if (-not $markers.ContainsKey("READY_TO_FOLLOW")) {
        [void]$blockers.Add("missing READY_TO_FOLLOW marker")
    }

    [pscustomobject]@{
        Ready = $markers.ContainsKey("READY_TO_FOLLOW") -and $markers["READY_TO_FOLLOW"] -eq "YES"
        Markers = $markers
        Blockers = @($blockers)
    }
}
