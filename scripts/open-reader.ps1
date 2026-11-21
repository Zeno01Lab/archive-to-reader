[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8772,
    [string]$Vault,
    [string]$DataDir,
    [switch]$Demo,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'On this platform, start reader/server.py with Python.' }
if ($Demo -and ($Vault -or $DataDir)) { throw 'Use -Demo by itself or specify a vault/data directory.' }

$projectRoot = [IO.Path]::GetDirectoryName($PSScriptRoot)
$serverPath = Join-Path $projectRoot 'reader\server.py'
$readerUrl = "http://127.0.0.1:$Port/"

function Find-ReaderPython {
    $candidates = @(
        @{ Name = 'py.exe'; Prefix = @('-3') },
        @{ Name = 'python.exe'; Prefix = @() }
    )
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command -or $command.Source -like '*\Microsoft\WindowsApps\python.exe') { continue }
        $check = $candidate.Prefix + @('-c', 'import sys; sys.exit(sys.version_info < (3, 10))')
        try {
            & $command.Source @check 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ Path = $command.Source; Prefix = $candidate.Prefix } }
        } catch {}
    }
    throw 'Python 3.10 or newer is required. Install it and put py.exe or python.exe on PATH.'
}

function Quote-WindowsArgument([string]$Value) {
    # Native programs expect a doubled final backslash before the closing quote.
    if ($Value.Contains('"')) { throw 'A path contains an invalid double quote.' }
    return '"' + ($Value -replace '(\\+)$', '$1$1') + '"'
}

function Get-ReaderHealth {
    try {
        return Invoke-RestMethod -Uri ($readerUrl + 'api/health') -TimeoutSec 2
    } catch {
        return $null
    }
}

function Test-PortListener {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $attempt = $client.ConnectAsync('127.0.0.1', $Port)
        return $attempt.Wait(500) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Assert-ReaderConfiguration($Health, $Paths) {
    if ($Health.app -ne 'archive-to-reader') {
        throw "Port $Port is serving another application. Choose a different -Port."
    }
    if ($Health.vault -ine $Paths[0] -or $Health.dataDir -ine $Paths[1]) {
        throw "Port $Port is already serving a different Clipping Cabinet vault or data directory. Choose a different -Port."
    }
}

if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) { throw 'The reader/server.py file is missing.' }
$python = Find-ReaderPython
$prefix = $python.Prefix
if ($Demo) {
    $vaultPath = Join-Path $projectRoot 'examples\vault'
    $dataPath = Join-Path $projectRoot 'workspace\.reader-demo'
} else {
    $vaultPath = Join-Path $projectRoot 'workspace\vault'
    $dataPath = Join-Path $projectRoot 'workspace\.reader'
    if ($Vault) { $vaultPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Vault) }
    if ($DataDir) { $dataPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DataDir) }
}

$canonicalPaths = & $python.Path @prefix -c 'from pathlib import Path; import json,sys; print(json.dumps([str(Path(p).resolve()) for p in sys.argv[1:]]))' $vaultPath $dataPath
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the vault and data paths.' }
$paths = ConvertFrom-Json -InputObject $canonicalPaths
if (-not (Test-Path -LiteralPath $paths[0] -PathType Container)) {
    if ($Demo -or $Vault) { throw "Vault directory not found: $($paths[0])" }
    [IO.Directory]::CreateDirectory($paths[0]) | Out-Null
}

$health = Get-ReaderHealth
if ($null -eq $health) {
    if (Test-PortListener) { throw "Port $Port is already in use. Choose a different -Port." }
    $arguments = @($prefix) + @('-B', (Quote-WindowsArgument $serverPath), '--port', [string]$Port)
    if ($Demo) {
        $arguments += '--demo'
    } else {
        $arguments += @('--vault', (Quote-WindowsArgument $paths[0]), '--data-dir', (Quote-WindowsArgument $paths[1]))
    }
    Start-Process -FilePath $python.Path -ArgumentList ($arguments -join ' ') -WorkingDirectory $projectRoot -WindowStyle Hidden
    for ($attempt = 0; $attempt -lt 25 -and $null -eq $health; $attempt++) {
        Start-Sleep -Milliseconds 200
        $health = Get-ReaderHealth
    }
    if ($null -eq $health) { throw "Clipping Cabinet did not start on port $Port. Run reader/server.py in a terminal to see its startup error." }
}
Assert-ReaderConfiguration $health $paths

if (-not $NoBrowser) { Start-Process $readerUrl }
Write-Output $readerUrl
