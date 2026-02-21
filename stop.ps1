# ═══════════════════════════════════════════════════════════════════════════════
# KNIGHTBOT CANONICAL SHUTDOWN SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$K = "F:\KnightBot"

function Get-ListeningConnections {
    param([Parameter(Mandatory=$true)][int[]]$Ports)
    $all = @()
    foreach ($p in $Ports) {
        $all += Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue
    }
    return @($all | Where-Object { $_ -and $_.OwningProcess })
}

function Format-ListenerSummary {
    param([Parameter(Mandatory=$true)]$Connections)
    if (-not $Connections -or $Connections.Count -eq 0) { return "(none)" }
    $pids = @($Connections | Select-Object -ExpandProperty OwningProcess -Unique)
    $procs = Get-Process -Id $pids -ErrorAction SilentlyContinue |
        Select-Object Id, ProcessName
    return ($Connections |
        Select-Object LocalPort, OwningProcess |
        Sort-Object LocalPort, OwningProcess |
        Format-Table -AutoSize | Out-String) + "`n" + ($procs | Format-Table -AutoSize | Out-String)
}

function Stop-ProcessHard {
    param(
        [Parameter(Mandatory=$true)][int]$ProcessId,
        [string]$Reason = ""
    )

    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Write-Host "  OK: Stop-Process killed PID $ProcessId $Reason" -ForegroundColor DarkGray
        return $true
    }
    catch {
        Write-Host "  WARN: Stop-Process failed for PID $ProcessId ${Reason}: $($_.Exception.Message)" -ForegroundColor Yellow
        try {
            # Fallback: taskkill can sometimes terminate stubborn process trees.
            & taskkill.exe /PID $ProcessId /T /F | Out-Null
            Write-Host "  OK: taskkill killed PID $ProcessId $Reason" -ForegroundColor DarkGray
            return $true
        }
        catch {
            Write-Host "  ERROR: taskkill failed for PID $ProcessId ${Reason}: $($_.Exception.Message)" -ForegroundColor Red
            return $false
        }
    }
}

function Invoke-DockerCompose {
    param(
        [Parameter(Mandatory=$true)][string[]]$Args
    )

    # Prefer the modern plugin (`docker compose`). If user has legacy `docker-compose`, fall back.
    try {
        $null = docker compose version 2>$null
        & docker compose @Args
        return $LASTEXITCODE
    }
    catch {
        & docker-compose @Args
        return $LASTEXITCODE
    }
}

Write-Host "`nStopping KnightBot...`n" -ForegroundColor Yellow

# Stop services by known listening ports (safer than killing all python/node)
$ports = @(3000, 8060, 8070, 8071, 8100, 7880, 7881)

$before = Get-ListeningConnections -Ports $ports
if ($before.Count -gt 0) {
    Write-Host "Listeners before stop:" -ForegroundColor DarkGray
    Write-Host (Format-ListenerSummary -Connections $before) -ForegroundColor DarkGray
}

# Retry loop: some processes briefly re-bind or take a moment to terminate.
$deadline = (Get-Date).AddSeconds(12)
do {
    $connections = Get-ListeningConnections -Ports $ports
    foreach ($conn in $connections) {
        $processId = $conn.OwningProcess
        $port = $conn.LocalPort
        if ($processId) {
            $null = Stop-ProcessHard -ProcessId $processId -Reason "(port $port)"
        }
    }

    Start-Sleep -Milliseconds 750
    $still = Get-ListeningConnections -Ports $ports
} while ($still.Count -gt 0 -and (Get-Date) -lt $deadline)

if ($still.Count -gt 0) {
    Write-Host "WARNING: Some listeners are still active after stop attempts:" -ForegroundColor Yellow
    Write-Host (Format-ListenerSummary -Connections $still) -ForegroundColor Yellow
}

# Best-effort: sometimes Node/FastAPI keep a socket open briefly after Stop-Process.
Start-Sleep -Seconds 2

Set-Location $K
Invoke-DockerCompose -Args @("down") 2>$null

# Also stop common non-compose containers that can block required ports.
# This repo historically started some containers manually (outside docker compose),
# e.g. a container literally named "Qdrant".
function Stop-DockerContainerIfRunning {
    param([Parameter(Mandatory=$true)][string]$Name)
    try {
        $running = docker ps --format "{{.Names}}" | Where-Object { $_ -eq $Name }
        if ($running) {
            docker stop $Name | Out-Null
            Write-Host "  OK: Stopped Docker container '$Name'" -ForegroundColor DarkGray
        }
    } catch {}
}

Stop-DockerContainerIfRunning -Name "Qdrant"
Stop-DockerContainerIfRunning -Name "mem0"
Stop-DockerContainerIfRunning -Name "openmemory-mcp"

Write-Host "`nOK: KnightBot stopped`n" -ForegroundColor Green
