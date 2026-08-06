param(
    [Parameter(Mandatory = $true)]
    [string]$Python,

    [Parameter(Mandatory = $true)]
    [string]$Wheel,

    [ValidateSet("Prompt", "DigitalLicense", "Skip")]
    [string]$ActivationMode = "Prompt",

    [ValidateSet("System", "Interactive")]
    [string]$WorkerSession = "System",

    [string]$WorkerUser = $env:USERNAME
)

$ErrorActionPreference = "Stop"

function Test-WindowsActivated {
    $WindowsApplicationId = "55c92734-d682-4d71-983e-d6ec3f16059f"
    $License = Get-CimInstance -ClassName SoftwareLicensingProduct `
        -Filter "ApplicationID='$WindowsApplicationId' AND LicenseStatus=1" |
        Where-Object { $_.PartialProductKey } |
        Select-Object -First 1
    return $null -ne $License
}

function Request-WindowsActivation {
    param([string]$Mode)

    if ($Mode -eq "Skip" -or (Test-WindowsActivated)) {
        return
    }

    $HasProductKey = $false
    if ($Mode -eq "Prompt") {
        Write-Host "Enter a Windows Home product key. Leave it blank to use an existing digital license."
        $SecureProductKey = Read-Host -AsSecureString "Windows product key"
        $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureProductKey)
        try {
            $ProductKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
            if ($ProductKey) {
                if ($ProductKey -notmatch '^[A-Za-z0-9]{5}(-[A-Za-z0-9]{5}){4}$') {
                    throw "The Windows product key must contain five groups of five characters."
                }
                $Service = Get-CimInstance -ClassName SoftwareLicensingService
                Invoke-CimMethod -InputObject $Service -MethodName InstallProductKey `
                    -Arguments @{ ProductKey = $ProductKey } | Out-Null
                $HasProductKey = $true
            }
        }
        finally {
            $ProductKey = $null
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
        }
    }

    # This contains no secret. It activates an installed key or asks Microsoft's
    # activation service for a digital entitlement already associated with the VM.
    & cscript.exe //NoLogo "$env:SystemRoot\System32\slmgr.vbs" /ato | Out-Host
    if (-not (Test-WindowsActivated)) {
        if ($HasProductKey) {
            throw "Windows did not activate with the supplied product key."
        }
        Write-Warning "No digital license activated automatically. Sign in and use the Activation troubleshooter before sealing the base VM."
    }
}

Request-WindowsActivation -Mode $ActivationMode

$Root = "C:\ProgramData\codex-vm"
$Runtime = Join-Path $Root "runtime"
$State = Join-Path $Root "state"
$Secrets = Join-Path $Root "secrets"
$EnvironmentManifest = Join-Path $Root "environment.json"

New-Item -ItemType Directory -Force $Root, $State, $Secrets | Out-Null
& $Python -m venv $Runtime
& "$Runtime\Scripts\python.exe" -m pip install --no-index $Wheel

$Action = New-ScheduledTaskAction `
    -Execute "$Runtime\Scripts\codex-vm.exe" `
    -Argument "serve --runtime native --environment-manifest $EnvironmentManifest --root $State --host 0.0.0.0 --port 8443 --certificate $Secrets\worker.crt --private-key $Secrets\worker.key --client-ca $Secrets\controller-ca.crt"
if ($WorkerSession -eq "Interactive") {
    $Trigger = New-ScheduledTaskTrigger -AtLogOn -User $WorkerUser
    $Principal = New-ScheduledTaskPrincipal -UserId $WorkerUser `
        -LogonType Interactive -RunLevel Highest
}
else {
    $Trigger = New-ScheduledTaskTrigger -AtStartup
    $Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
}
$Settings = New-ScheduledTaskSettingsSet -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask `
    -TaskName "CodexVmWorker" `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Force | Out-Null

Write-Host "Native Windows worker installed for $WorkerSession execution. Inject per-VM certificates into $Secrets before boot."
