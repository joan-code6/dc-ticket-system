#!/usr/bin/env pwsh
# Discord Ticket Bot - Development Runner (PowerShell)
# Restarts the bot automatically when Python/JSON files change in bot/

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# Load token from .env
$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and $line -notlike "#*" -and $line -like "*=*") {
            $key, $value = $line.Split("=", 2)
            Set-Item -Path "env:$key" -Value $value.Trim('"', "'")
        }
    }
}
if ($env:DC_TOKEN -and -not $env:DISCORD_BOT_TOKEN) {
    $env:DISCORD_BOT_TOKEN = $env:DC_TOKEN
}

if (-not $env:DISCORD_BOT_TOKEN) {
    Write-Host "Error: DISCORD_BOT_TOKEN is not set. Add DC_TOKEN to .env or set DISCORD_BOT_TOKEN."
    exit 1
}

try {
    $null = Get-Command "python" -ErrorAction Stop
} catch {
    Write-Host "Error: Python is not installed or not in PATH."
    exit 1
}

Write-Host "Starting bot with auto-reload on file changes..."
Write-Host "Watching: bot/**/*.py"
Write-Host ""

# Build a map of file paths -> last write time for change tracking
$fileTimes = @{}
Get-ChildItem -Path "bot" -Recurse -Include "*.py" |
    Where-Object { $_.FullName -notmatch '__pycache__' } |
    ForEach-Object { $fileTimes[$_.FullName] = $_.LastWriteTime }

while ($true) {
    Write-Host "[run] Starting bot..."
    $process = Start-Process -FilePath "python" -ArgumentList @("-u", "bot/main.py") -NoNewWindow -PassThru
    Write-Host "[run] Bot started (PID: $($process.Id))"

    $running = $true
    while ($running) {
        Start-Sleep -Seconds 2

        if ($process.HasExited) {
            Write-Host "[run] Bot process exited with code $($process.ExitCode)."
            $running = $false
            break
        }

        # Check for any changed files since our last scan
        $changed = $false
        Get-ChildItem -Path "bot" -Recurse -Include "*.py" |
            Where-Object { $_.FullName -notmatch '__pycache__' } |
            ForEach-Object {
                $key = $_.FullName
                $lastTime = $fileTimes[$key]
                $currentTime = $_.LastWriteTime
                if (-not $lastTime -or $currentTime -ne $lastTime) {
                    $fileTimes[$key] = $currentTime
                    $changed = $true
                }
            }

        if ($changed) {
            Write-Host "[run] Change detected. Restarting..."
            $process.Kill()
            $process.WaitForExit()
            $running = $false
        }
    }

    Start-Sleep -Seconds 1
}
