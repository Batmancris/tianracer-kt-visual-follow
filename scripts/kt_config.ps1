Set-StrictMode -Version Latest

function Get-KtLocalRobotConfigValues {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $localConfigPath = Join-Path $repoRoot "config\local.robot.ps1"

    $emptyConfig = [pscustomobject]@{
        RobotIp         = $null
        RobotUser       = $null
        RosbridgePort   = $null
        MjpegPort       = $null
        RemoteWorkspace = $null
        VideoDevice     = $null
        LidarDevice     = $null
    }

    if (-not (Test-Path -LiteralPath $localConfigPath)) {
        return $emptyConfig
    }

    return & {
        $KT_ROBOT_IP = $null
        $KT_ROBOT_USER = $null
        $KT_ROSBRIDGE_PORT = $null
        $KT_MJPEG_PORT = $null
        $KT_REMOTE_WORKSPACE = $null
        $KT_VIDEO_DEVICE = $null
        $KT_LIDAR_DEVICE = $null

        . $localConfigPath

        [pscustomobject]@{
            RobotIp         = $KT_ROBOT_IP
            RobotUser       = $KT_ROBOT_USER
            RosbridgePort   = $KT_ROSBRIDGE_PORT
            MjpegPort       = $KT_MJPEG_PORT
            RemoteWorkspace = $KT_REMOTE_WORKSPACE
            VideoDevice     = $KT_VIDEO_DEVICE
            LidarDevice     = $KT_LIDAR_DEVICE
        }
    }
}

function Resolve-KtStringConfigValue {
    param(
        [AllowNull()]
        [string]$CommandLineValue,
        [AllowNull()]
        [string]$LocalConfigValue,
        [Parameter(Mandatory = $true)]
        [string]$EnvironmentVariableName,
        [Parameter(Mandatory = $true)]
        [string]$DefaultValue
    )

    foreach ($candidate in @(
        $CommandLineValue,
        $LocalConfigValue,
        [Environment]::GetEnvironmentVariable($EnvironmentVariableName)
    )) {
        if ($null -ne $candidate) {
            $trimmed = $candidate.Trim()
            if ($trimmed.Length -gt 0) {
                return $trimmed
            }
        }
    }

    return $DefaultValue
}

function Resolve-KtIntConfigValue {
    param(
        [AllowNull()]
        [int]$CommandLineValue,
        [AllowNull()]
        [object]$LocalConfigValue,
        [Parameter(Mandatory = $true)]
        [string]$EnvironmentVariableName,
        [Parameter(Mandatory = $true)]
        [int]$DefaultValue
    )

    foreach ($candidate in @(
        $CommandLineValue,
        $LocalConfigValue,
        [Environment]::GetEnvironmentVariable($EnvironmentVariableName)
    )) {
        if ($null -eq $candidate) {
            continue
        }

        $text = "$candidate".Trim()
        if ($text.Length -eq 0) {
            continue
        }

        $value = [int]$text
        if ($value -le 0) {
            continue
        }

        return $value
    }

    return $DefaultValue
}

function Get-KtRobotConfig {
    param(
        [string]$RobotIp,
        [string]$RobotUser,
        [Nullable[int]]$RosbridgePort,
        [Nullable[int]]$MjpegPort,
        [string]$RemoteWorkspace,
        [string]$VideoDevice,
        [string]$LidarDevice
    )

    $localConfig = Get-KtLocalRobotConfigValues

    return [pscustomobject]@{
        RobotIp         = Resolve-KtStringConfigValue -CommandLineValue $RobotIp -LocalConfigValue $localConfig.RobotIp -EnvironmentVariableName "KT_ROBOT_IP" -DefaultValue "10.217.185.241"
        RobotUser       = Resolve-KtStringConfigValue -CommandLineValue $RobotUser -LocalConfigValue $localConfig.RobotUser -EnvironmentVariableName "KT_ROBOT_USER" -DefaultValue "sunrise"
        RosbridgePort   = Resolve-KtIntConfigValue -CommandLineValue $RosbridgePort -LocalConfigValue $localConfig.RosbridgePort -EnvironmentVariableName "KT_ROSBRIDGE_PORT" -DefaultValue 9090
        MjpegPort       = Resolve-KtIntConfigValue -CommandLineValue $MjpegPort -LocalConfigValue $localConfig.MjpegPort -EnvironmentVariableName "KT_MJPEG_PORT" -DefaultValue 8080
        RemoteWorkspace = Resolve-KtStringConfigValue -CommandLineValue $RemoteWorkspace -LocalConfigValue $localConfig.RemoteWorkspace -EnvironmentVariableName "KT_REMOTE_WORKSPACE" -DefaultValue "~/tianracer_ros2_ws"
        VideoDevice     = Resolve-KtStringConfigValue -CommandLineValue $VideoDevice -LocalConfigValue $localConfig.VideoDevice -EnvironmentVariableName "KT_VIDEO_DEVICE" -DefaultValue "/dev/video0"
        LidarDevice     = Resolve-KtStringConfigValue -CommandLineValue $LidarDevice -LocalConfigValue $localConfig.LidarDevice -EnvironmentVariableName "KT_LIDAR_DEVICE" -DefaultValue "/dev/tianbot_lidar"
    }
}
