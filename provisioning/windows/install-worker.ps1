param(
    [Parameter(Mandatory = $true)]
    [string]$Python,

    [string]$Wheel,

    [string]$SourceDirectory,

    [switch]$PortablePython,

    [ValidateSet("Prompt", "DigitalLicense", "Skip")]
    [string]$ActivationMode = "Prompt",

    [ValidateSet("System", "Interactive")]
    [string]$WorkerSession = "System",

    [string]$WorkerUser = $env:USERNAME
)

$ErrorActionPreference = "Stop"
if ([bool]$Wheel -eq [bool]$SourceDirectory) {
    throw "Specify exactly one of -Wheel or -SourceDirectory."
}
if ($PortablePython -and $Wheel) {
    throw "Portable Python installation requires -SourceDirectory, not -Wheel."
}

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
$AclPrincipals = @(
    "*S-1-5-18:(OI)(CI)F",
    "*S-1-5-32-544:(OI)(CI)F"
)
if ($WorkerSession -eq "Interactive") {
    $Account = [Security.Principal.NTAccount]::new($WorkerUser)
    $WorkerSid = $Account.Translate([Security.Principal.SecurityIdentifier]).Value
    $AclPrincipals += "*$($WorkerSid):(OI)(CI)M"
}
$AclArguments = @($Root, "/inheritance:r", "/grant:r") + $AclPrincipals
& icacls.exe @AclArguments | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to restrict the worker directory ACL"
}

if ($PortablePython) {
    $WorkerPython = $Python
    $PackageDestination = Join-Path $Runtime "codex_vm"
    New-Item -ItemType Directory -Force $PackageDestination | Out-Null
    Copy-Item -Recurse -Force (Join-Path $SourceDirectory "*") $PackageDestination
}
else {
    & $Python -m venv $Runtime
    $WorkerPython = "$Runtime\Scripts\python.exe"
    if ($Wheel) {
        & $WorkerPython -m pip install --no-index $Wheel
    }
    else {
        $SitePackages = & $WorkerPython -c `
            "import sysconfig; print(sysconfig.get_paths()['purelib'])"
        Copy-Item -Recurse -Force $SourceDirectory (Join-Path $SitePackages "codex_vm")
    }
}

$Action = New-ScheduledTaskAction `
    -Execute $WorkerPython `
    -Argument "-m codex_vm.cli serve --runtime native --environment-manifest $EnvironmentManifest --root $State --host 0.0.0.0 --port 8443 --token-file $Secrets\controller.token"
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

Remove-NetFirewallRule -DisplayName "Codex VM worker control" -ErrorAction SilentlyContinue
New-NetFirewallRule `
    -DisplayName "Codex VM worker control" `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort 8443 `
    -RemoteAddress "10.0.2.2" `
    -Profile Any | Out-Null

Write-Host "Native Windows worker installed for $WorkerSession execution. Inject a per-VM controller.token into $Secrets before boot."
