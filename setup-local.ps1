$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath '.env')) {
    $keyBytes = New-Object byte[] 64
    $keyGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $keyGenerator.GetBytes($keyBytes) } finally { $keyGenerator.Dispose() }
    $localKey = [Convert]::ToBase64String($keyBytes)
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot '.env'), "PUMP_SECRET_KEY=$localKey`n")
    Write-Host 'Created private local signing key. Keep .env private.'
} else {
    Write-Host 'Existing local signing key retained.'
}

# Prepare protected backup folders and start the container stack.
& (Join-Path $PSScriptRoot "setup-backups.ps1")
