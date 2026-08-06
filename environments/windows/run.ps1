param(
    [Parameter(Position = 0)]
    [string]$Operation = ""
)

$ErrorActionPreference = "Stop"
$Output = $env:CODEX_VM_OUTPUT
if (-not $Output) {
    throw "CODEX_VM_OUTPUT is not set"
}

if ($Operation -eq "smoke") {
    [Environment]::OSVersion.VersionString | Set-Content (Join-Path $Output "windows-version.txt")
    exit 0
}

Write-Error "unsupported example operation: $Operation"
exit 64
