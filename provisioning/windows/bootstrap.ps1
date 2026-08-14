$ErrorActionPreference = "Stop"
$PayloadRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Configuration = Get-Content (Join-Path $PayloadRoot "bootstrap-config.json") -Raw |
    ConvertFrom-Json

function Disable-BuildAutoLogon {
    $Winlogon = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
    Set-ItemProperty $Winlogon -Name AutoAdminLogon -Value "0"
    Remove-ItemProperty $Winlogon -Name DefaultPassword -ErrorAction SilentlyContinue
    Remove-ItemProperty $Winlogon -Name AutoLogonCount -ErrorAction SilentlyContinue
}

try {
    Write-Host "Expanding the pinned private Python runtime..."
    $PythonRoot = "C:\ProgramData\codex-vm\runtime"
    New-Item -ItemType Directory -Force $PythonRoot | Out-Null
    $PythonArchive = Join-Path $PayloadRoot $Configuration.python_archive
    Expand-Archive -Path $PythonArchive -DestinationPath $PythonRoot -Force
    $Python = Join-Path $PythonRoot "python.exe"
    if (-not (Test-Path $Python)) {
        throw "The Python runtime archive did not contain python.exe"
    }
    $WorkerSource = Join-Path $PayloadRoot "codex_vm"
    if (-not (Test-Path (Join-Path $WorkerSource "__init__.py"))) {
        throw "The provisioning payload does not contain the codex_vm package"
    }

    Write-Host "Installing and activating the Windows worker..."
    & (Join-Path $PayloadRoot "install-worker.ps1") `
        -Python $Python `
        -SourceDirectory $WorkerSource `
        -PortablePython `
        -ActivationMode $Configuration.activation_mode `
        -WorkerSession $Configuration.worker_session `
        -WorkerUser $Configuration.worker_user

    Disable-BuildAutoLogon
    Remove-Item "C:\Windows\Panther\unattend.xml" -Force -ErrorAction SilentlyContinue
    Remove-Item "C:\Windows\Panther\Unattend\unattend.xml" `
        -Force -ErrorAction SilentlyContinue

    $WindowsApplicationId = "55c92734-d682-4d71-983e-d6ec3f16059f"
    $Activated = $null -ne (Get-CimInstance -ClassName SoftwareLicensingProduct `
        -Filter "ApplicationID='$WindowsApplicationId' AND LicenseStatus=1" |
        Where-Object { $_.PartialProductKey } |
        Select-Object -First 1)
    $Evidence = [ordered]@{
        schema = 1
        provisioned_at = (Get-Date).ToUniversalTime().ToString("o")
        windows_edition = (Get-ComputerInfo).WindowsProductName
        windows_version = (Get-ComputerInfo).WindowsVersion
        activated = $Activated
        worker_session = $Configuration.worker_session
    }
    $Evidence | ConvertTo-Json |
        Set-Content -Encoding utf8 "C:\ProgramData\codex-vm\base-ready.json"

    Write-Host ""
    Write-Host "Windows base provisioning completed successfully." -ForegroundColor Green
    Write-Host "The VM will shut down in ten seconds."
    Start-Sleep -Seconds 10
    Stop-Computer -Force
}
catch {
    Write-Host $_ -ForegroundColor Red
    Write-Host "Provisioning did not complete. The VM will remain running for inspection."
    Read-Host "Press Enter after recording the error"
    exit 1
}
