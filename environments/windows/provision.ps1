param(
    [Parameter(Mandatory = $true)]
    [string]$Reference,

    [Parameter(Mandatory = $true)]
    [string]$Digest,

    [Parameter(Mandatory = $true)]
    [string]$SetEnvironmentScript,

    [string]$VsCodeSystemInstaller
)

$ErrorActionPreference = "Stop"
$EnvironmentRoot = "C:\environment"
New-Item -ItemType Directory -Force $EnvironmentRoot | Out-Null
Copy-Item -Force "$PSScriptRoot\run.ps1" "$EnvironmentRoot\run.ps1"

if ($VsCodeSystemInstaller) {
    $Process = Start-Process -Wait -PassThru $VsCodeSystemInstaller `
        -ArgumentList "/VERYSILENT", "/NORESTART", "/ALLUSERS"
    if ($Process.ExitCode -ne 0) {
        throw "Visual Studio Code installation failed with exit code $($Process.ExitCode)"
    }
}

& $SetEnvironmentScript -Reference $Reference -Digest $Digest
