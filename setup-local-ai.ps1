$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & docker compose -p hpcl_pump -f compose.yaml -f compose.ai-download.yaml up -d --build ollama
    if ($LASTEXITCODE -ne 0) { throw 'Could not start local model downloader.' }
    try {
        & docker compose -p hpcl_pump -f compose.yaml exec -T ollama ollama pull qwen3:1.7b
        if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Retry this script; downloaded pieces are retained.' }
    } finally {
        # Always remove the temporary Internet connection, even on failure.
        & docker compose -p hpcl_pump -f compose.yaml up -d ollama
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Isolation restart failed. Run docker compose -p hpcl_pump -f compose.yaml up -d ollama before using AI.' }
    }
    & docker compose -p hpcl_pump -f compose.yaml up -d --build web station2 portal backup
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the pump services.' }
    Write-Host 'Local AI model installed. Open /ai-briefing/ as the owner.'
} finally { Pop-Location }
