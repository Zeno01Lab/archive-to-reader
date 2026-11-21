[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8772,
    [ValidatePattern('^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')]
    [string]$At = '20:00',
    [string]$Vault,
    [string]$DataDir,
    [switch]$Demo
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This script uses Windows Task Scheduler.' }
if ($Demo -and ($Vault -or $DataDir)) { throw 'Use -Demo by itself or specify a vault/data directory.' }

$projectRoot = [IO.Path]::GetDirectoryName($PSScriptRoot)
$launcher = Join-Path $PSScriptRoot 'open-reader.ps1'
$windowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$taskName = "Archive to Reader (port $Port)"
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'The open-reader.ps1 file is missing.' }
if (-not (Test-Path -LiteralPath $windowsPowerShell -PathType Leaf)) { throw 'Windows PowerShell was not found.' }

function Quote-WindowsArgument([string]$Value) {
    if ($Value.Contains('"')) { throw 'A path contains an invalid double quote.' }
    return '"' + ($Value -replace '(\\+)$', '$1$1') + '"'
}

# Limit execution-policy selection to this scheduled PowerShell process.
$arguments = @(
    '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'RemoteSigned', '-WindowStyle', 'Hidden',
    '-File', (Quote-WindowsArgument $launcher), '-Port', [string]$Port
)
if ($Demo) { $arguments += '-Demo' }
if ($Vault) {
    $path = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Vault)
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "Vault directory not found: $path" }
    $arguments += @('-Vault', (Quote-WindowsArgument $path))
}
if ($DataDir) {
    $path = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DataDir)
    $arguments += @('-DataDir', (Quote-WindowsArgument $path))
}

$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$description = 'Open Clipping Cabinet in the signed-in user session.'
if (-not $PSCmdlet.ShouldProcess($taskName, "Schedule daily at $At in the interactive session for $account")) { return }

$existing = Get-ScheduledTask -TaskPath '\' -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    $oldAction = @($existing.Actions)
    $owned = $existing.Description -eq $description -and $oldAction.Count -eq 1 -and
        $oldAction[0].Arguments.IndexOf((Quote-WindowsArgument $launcher), [StringComparison]::OrdinalIgnoreCase) -ge 0
    if (-not $owned) { throw "A different task already uses the name '$taskName'. Choose a different -Port." }
}
$clockTime = [TimeSpan]::ParseExact($At, 'hh\:mm', [Globalization.CultureInfo]::InvariantCulture)
$action = New-ScheduledTaskAction -Execute $windowsPowerShell -Argument ($arguments -join ' ') -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At ([DateTime]::Today.Add($clockTime))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskPath '\' -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description $description -Force | Out-Null
$task = Get-ScheduledTask -TaskPath '\' -TaskName $taskName
$task | Select-Object TaskName, State, @{ Name = 'NextRun'; Expression = { ($task | Get-ScheduledTaskInfo).NextRunTime } }
