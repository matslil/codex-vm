param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[^\s@]+$')]
    [string]$Reference,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^sha256:[0-9a-f]{64}$')]
    [string]$Digest,

    [string]$Destination = "C:\ProgramData\codex-vm\environment.json"
)

$ErrorActionPreference = "Stop"
$Parent = Split-Path -Parent $Destination
New-Item -ItemType Directory -Force $Parent | Out-Null

$Manifest = [ordered]@{
    schema = 1
    reference = $Reference
    digest = $Digest
}
$Temporary = "$Destination.new"
$Manifest | ConvertTo-Json | Set-Content -Encoding utf8 $Temporary
Move-Item -Force $Temporary $Destination
Write-Host "Selected native environment $Reference@$Digest"
