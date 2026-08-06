param(
    [Parameter(Position = 0)]
    [string]$Operation = ""
)

$ErrorActionPreference = "Stop"

if ($Operation -eq "smoke") {
    [Environment]::OSVersion.VersionString | Set-Content C:\job\output\windows-version.txt
    exit 0
}

Write-Error "unsupported example operation: $Operation"
exit 64

