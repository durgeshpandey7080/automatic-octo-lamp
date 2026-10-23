param(
    [Parameter(Mandatory=$true)][ValidatePattern('^pump-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}\.pumpbackup$')][string]$BackupFile,
    [switch]$Apply,
    [string]$ConfirmRestore
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
$docker = Join-Path $env:ProgramFiles 'Docker/Docker/resources/bin/docker.exe'
function Run-Docker { & $docker @args; if ($LASTEXITCODE -ne 0) { throw 'Recovery command failed. Application services remain stopped if replacement was started. See BACKUP_RECOVERY.md.' } }
$backupPath = Join-Path (Split-Path $PSScriptRoot -Parent) "pump-backups/$BackupFile"
if (-not (Test-Path -LiteralPath $backupPath)) { throw 'Copy the selected encrypted bundle to pump-backups first.' }
if (-not $Apply) {
    Run-Docker compose -p hpcl_pump -f compose.yaml run --rm --no-deps backup python backup_runner.py verify --bundle "/backups/$BackupFile"
    Write-Host 'Recovery rehearsal passed. Live databases were not replaced.'
    return
}
if ($ConfirmRestore -cne 'RESTORE BOTH ORGANISATIONS') { throw 'Applying recovery requires -ConfirmRestore "RESTORE BOTH ORGANISATIONS". It replaces both stations with older records.' }
Run-Docker compose -p hpcl_pump -f compose.yaml stop backup web station2
$stageName = 'recovery-stage-' + [guid]::NewGuid().ToString('N')
Run-Docker compose -p hpcl_pump -f compose.yaml run --rm --no-deps backup python backup_runner.py restore-stage --bundle "/backups/$BackupFile" --destination "/backups/$stageName"
# Make a verified encrypted safety bundle of the current databases before replacement.
Run-Docker compose -p hpcl_pump -f compose.yaml run --rm --no-deps backup python backup_runner.py once
Run-Docker compose -p hpcl_pump -f compose.yaml run --rm --no-deps --user 0 -v hpcl_pump_pump_data:/restore/station1 -v hpcl_pump_station2_data:/restore/station2 backup python restore_apply.py "/backups/$stageName"
Run-Docker compose -p hpcl_pump -f compose.yaml up -d web station2 portal backup
Write-Host 'Both station databases and uploaded documents restored. Private settings and code were retained; see the guide for complete PC-loss recovery.'

} finally { Pop-Location }
