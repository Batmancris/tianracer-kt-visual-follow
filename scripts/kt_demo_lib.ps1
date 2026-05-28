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
