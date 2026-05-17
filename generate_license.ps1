param(
    [Parameter(Mandatory = $true)]
    [string]$MachineCode,

    [string]$LicensedTo = "",

    [string]$ExpiresAt = "",

    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$PrivateKey = Join-Path $PSScriptRoot "private_key.pem"
$Tool = Join-Path $PSScriptRoot "license_tool.py"

if (-not (Test-Path -LiteralPath $PrivateKey)) {
    throw "private_key.pem not found."
}

if (-not (Test-Path -LiteralPath $Tool)) {
    throw "license_tool.py not found."
}

if (-not $Output) {
    $SafeOwner = if ($LicensedTo) { $LicensedTo } else { "client" }
    $SafeOwner = $SafeOwner -replace '[^\p{L}\p{Nd}_-]', '_'
    $SafeCode = $MachineCode -replace '[^\p{L}\p{Nd}_-]', '_'
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $Output = "license_${SafeOwner}_${SafeCode}_${Timestamp}.lic"
}

$argsList = @(
    $Tool,
    "issue",
    "--machine-code", $MachineCode,
    "--private-key", $PrivateKey,
    "--out", $Output,
    "--licensed-to", $LicensedTo
)

if ($ExpiresAt) {
    $argsList += @("--expires-at", $ExpiresAt)
}

python @argsList

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "License generated: $(Join-Path $PSScriptRoot $Output)"
Write-Host "Put license.lic next to zhijianwushuang.exe."
