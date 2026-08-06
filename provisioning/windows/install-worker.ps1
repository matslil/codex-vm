param(
    [Parameter(Mandatory = $true)]
    [string]$Python,

    [Parameter(Mandatory = $true)]
    [string]$Wheel
)

$ErrorActionPreference = "Stop"
$Root = "C:\ProgramData\codex-vm"
$Runtime = Join-Path $Root "runtime"
$State = Join-Path $Root "state"
$Secrets = Join-Path $Root "secrets"

New-Item -ItemType Directory -Force $Root, $State, $Secrets | Out-Null
& $Python -m venv $Runtime
& "$Runtime\Scripts\python.exe" -m pip install --no-index $Wheel

$Action = New-ScheduledTaskAction `
    -Execute "$Runtime\Scripts\codex-vm.exe" `
    -Argument "serve --root $State --host 0.0.0.0 --port 8443 --certificate $Secrets\worker.crt --private-key $Secrets\worker.key --client-ca $Secrets\controller-ca.crt"
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask `
    -TaskName "CodexVmWorker" `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Force | Out-Null

Write-Host "Worker installed. Inject per-VM certificates into $Secrets before boot."

