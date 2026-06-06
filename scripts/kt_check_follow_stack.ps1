param(
    [string]$RobotIp = "10.138.249.241",
    [string]$User = "sunrise",
    [string]$BoardScriptDir = "/home/sunrise/kt_scripts"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$remoteCommand = "bash $BoardScriptDir/check_kt_follow_stack.sh"
$target = "$User@$RobotIp"

Write-Host "Remote command:" -ForegroundColor Cyan
Write-Host "ssh $target `"$remoteCommand`""

& ssh $target $remoteCommand
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    exit $exitCode
}
