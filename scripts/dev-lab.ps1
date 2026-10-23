param([ValidateSet('Init','Build','Seed','Start','Verify','Stop')][string]$Action = 'Verify')
$ErrorActionPreference = 'Stop'
$devRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $devRoot
$envFile = Join-Path $devRoot '.env.dev'
$composeArgs = @('compose','--env-file',$envFile,'-f',(Join-Path $devRoot 'compose.dev.yaml'))
function Invoke-DevDocker {
    param([string[]]$DockerArguments)
    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw 'Development Docker command failed; existing volumes were retained.' }
}
if ($Action -eq 'Init') {
    if (-not (Test-Path -LiteralPath $envFile)) {
        $keyBytes = New-Object byte[] 64
        $passwordBytes = New-Object byte[] 24
        $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $generator.GetBytes($keyBytes); $generator.GetBytes($passwordBytes) } finally { $generator.Dispose() }
        $devKey = [Convert]::ToBase64String($keyBytes)
        $devPassword = [Convert]::ToBase64String($passwordBytes)
        [IO.File]::WriteAllText($envFile, "PUMP_DEV_SECRET_KEY=$devKey`nPUMP_DEV_OWNER_PASSWORD=$devPassword`n", [Text.UTF8Encoding]::new($false))
    }
    Write-Host 'Private .env.dev is ready. Synthetic login: synthetic-owner. Read its password from .env.dev; do not share or commit it.'
    exit
}
if (-not (Test-Path -LiteralPath $envFile)) { throw 'Run scripts/dev-lab.ps1 Init first.' }
switch ($Action) {
    'Build' { Invoke-DevDocker ($composeArgs + @('build','web')) }
    'Seed' {
        foreach ($stationService in @('web','station2')) {
            Invoke-DevDocker ($composeArgs + @('run','--rm','--no-deps',$stationService,'python','manage.py','migrate','--noinput'))
            Invoke-DevDocker ($composeArgs + @('run','--rm','--no-deps',$stationService,'python','manage.py','synthetic_lab','--confirm-synthetic'))
        }
    }
    'Start' { Invoke-DevDocker ($composeArgs + @('up','-d','--no-build')); Write-Host 'Synthetic-only lab: http://127.0.0.1:8015/' }
    'Verify' {
        Invoke-DevDocker -DockerArguments @('run','--rm','-e','PUMP_DB_PATH=/tmp/synthetic.sqlite3','pump-dev-lab:local','python','manage.py','test','--noinput')
        foreach ($stationService in @('web','station2')) {
            Invoke-DevDocker ($composeArgs + @('exec','-T',$stationService,'python','manage.py','check'))
        }
    }
    'Stop' { Invoke-DevDocker ($composeArgs + @('stop')) }
}
