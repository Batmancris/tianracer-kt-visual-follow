param(
    [string]$RobotIp = "10.138.249.241",
    [string]$User = "sunrise",
    [string]$BoardScriptDir = "/home/sunrise/kt_scripts",
    [switch]$ForceCameraRelease
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$remoteArgs = New-Object System.Collections.Generic.List[string]
$remoteArgs.Add("bash")
$remoteArgs.Add("$BoardScriptDir/stop_kt_follow_stack.sh")
if ($ForceCameraRelease) {
    $remoteArgs.Add("--force-camera-release")
}

$remoteCommand = ($remoteArgs -join " ")

$target = "$User@$RobotIp"
Write-Host "Remote command:" -ForegroundColor Cyan
Write-Host "ssh $target `"$remoteCommand`""

& ssh $target $remoteCommand
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    exit $exitCode
}
