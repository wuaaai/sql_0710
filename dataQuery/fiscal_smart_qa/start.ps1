$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

Write-Host "Current project:" $projectDir
Write-Host "Starting Fiscal Smart QA..."

python main.py
