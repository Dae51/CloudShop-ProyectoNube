param(
  [string]$Config = ".\cloudshop-test-config.example.json",
  [ValidateSet("all", "case1", "case2", "case3", "case4")]
  [string]$Case = "all",
  [switch]$Apply
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "python"

if (Test-Path "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe") {
  $Python = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
}

$ArgsList = @("$ScriptDir\cloudshop_integration.py", "--config", (Join-Path $ScriptDir $Config), "--case", $Case)
if ($Apply) {
  $ArgsList += "--apply"
}

& $Python @ArgsList

