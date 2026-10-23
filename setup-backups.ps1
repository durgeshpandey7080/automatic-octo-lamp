$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
foreach ($folderName in @('pump-backups', 'pump-backups-secondary', 'pump-recovery')) {
    $folderPath = Join-Path (Split-Path $PSScriptRoot -Parent) $folderName
    New-Item -ItemType Directory -Force -Path $folderPath | Out-Null
    & icacls.exe $folderPath /inheritance:r /grant:r "*${ownerSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not protect the backup folder permissions.' }
}
$keyPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'pump-recovery/backup.key'
if (-not (Test-Path -LiteralPath $keyPath)) {
    $randomBytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($randomBytes) } finally { $generator.Dispose() }
    $backupKey = [Convert]::ToBase64String($randomBytes).Replace('+','-').Replace('/','_')
    [IO.File]::WriteAllText($keyPath, $backupKey, [Text.UTF8Encoding]::new($false))
}
$docker = Join-Path $env:ProgramFiles 'Docker/Docker/resources/bin/docker.exe'
& $docker compose -p hpcl_pump -f compose.yaml build web
if ($LASTEXITCODE -ne 0) { throw 'Docker image build failed.' }
& $docker run --rm --user 0 -v hpcl_pump_backup_requests:/requests hpcl_pump-web python -c "import os; os.chown('/requests',10001,10001); os.chmod('/requests',0o700)"
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare backup requests volume.' }
& $docker compose -p hpcl_pump -f compose.yaml up -d
if ($LASTEXITCODE -ne 0) { throw 'Backup service startup failed.' }
Write-Host 'Encrypted hourly backups enabled. Keep the recovery key private and save a protected copy separately from this PC.'
