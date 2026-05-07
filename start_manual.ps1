param(
    [string]$MySqlHost = "127.0.0.1",
    [int]$MySqlPort = 3306,
    [string]$DbUser,
    [string]$DbPassword,
    [string]$DbName,
    [int]$BackendPort = 8080,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"

if (-not (Test-Path $backendDir)) {
    Write-Host "Backend folder not found: $backendDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $frontendDir)) {
    Write-Host "Frontend folder not found: $frontendDir" -ForegroundColor Red
    exit 1
}

$pythonExe = Join-Path $backendDir "venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"
}
if (-not (Test-Path $pythonExe)) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $pythonExe = $pythonCmd.Source
    } else {
        Write-Host "Python not found. Create a backend venv or install Python first." -ForegroundColor Red
        exit 1
    }
}

$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    Write-Host "npm not found. Install Node.js first." -ForegroundColor Red
    exit 1
}

function Test-MySqlCredential {
    param(
        [string]$PythonExePath,
        [string]$DbHost,
        [int]$Port,
        [string]$User,
        [string]$Password,
        [string]$Database
    )

    $env:DMS_TEST_DB_HOST = $DbHost
    $env:DMS_TEST_DB_PORT = "$Port"
    $env:DMS_TEST_DB_USER = $User
    $env:DMS_TEST_DB_PASSWORD = $Password
    $env:DMS_TEST_DB_NAME = $Database

    $probeScript = @"
import os
import sys
import pymysql

try:
    conn = pymysql.connect(
        host=os.environ['DMS_TEST_DB_HOST'],
        port=int(os.environ['DMS_TEST_DB_PORT']),
        user=os.environ['DMS_TEST_DB_USER'],
        password=os.environ.get('DMS_TEST_DB_PASSWORD', ''),
        database=os.environ['DMS_TEST_DB_NAME'],
        connect_timeout=4,
    )
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
"@

    & $PythonExePath -c $probeScript
    $ok = $LASTEXITCODE -eq 0

    Remove-Item Env:DMS_TEST_DB_HOST -ErrorAction SilentlyContinue
    Remove-Item Env:DMS_TEST_DB_PORT -ErrorAction SilentlyContinue
    Remove-Item Env:DMS_TEST_DB_USER -ErrorAction SilentlyContinue
    Remove-Item Env:DMS_TEST_DB_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:DMS_TEST_DB_NAME -ErrorAction SilentlyContinue

    return $ok
}

# Resolve DB settings for manual/local runs without forcing Docker defaults.
if ([string]::IsNullOrWhiteSpace($DbUser)) {
    if ([string]::IsNullOrWhiteSpace($env:DB_USER)) {
        $DbUser = "root"
    } else {
        $DbUser = $env:DB_USER
    }
}

if ($null -eq $DbPassword) {
    if ($null -eq $env:DB_PASSWORD) {
        $DbPassword = ""
    } else {
        $DbPassword = $env:DB_PASSWORD
    }
}

if ([string]::IsNullOrWhiteSpace($DbName)) {
    if ([string]::IsNullOrWhiteSpace($env:DB_NAME)) {
        $DbName = "distribution_management_system"
    } else {
        $DbName = $env:DB_NAME
    }
}

$candidateCredentials = @()

# 1) Explicit CLI args if provided.
if (
    -not [string]::IsNullOrWhiteSpace($PSBoundParameters['DbUser']) -or
    $PSBoundParameters.ContainsKey('DbPassword') -or
    -not [string]::IsNullOrWhiteSpace($PSBoundParameters['DbName'])
) {
    $candidateCredentials += [PSCustomObject]@{
        Source = "command arguments"
        User = $DbUser
        Password = $DbPassword
        Name = $DbName
    }
}

# 2) Existing shell environment vars.
if (-not [string]::IsNullOrWhiteSpace($env:DB_USER)) {
    $candidateCredentials += [PSCustomObject]@{
        Source = "environment variables"
        User = $env:DB_USER
        Password = $(if ($null -eq $env:DB_PASSWORD) { "" } else { $env:DB_PASSWORD })
        Name = $(if ([string]::IsNullOrWhiteSpace($env:DB_NAME)) { $DbName } else { $env:DB_NAME })
    }
}

# 3) Known local profiles.
$candidateCredentials += [PSCustomObject]@{
    Source = "docker app user defaults"
    User = "dms_user"
    Password = "dms_password"
    Name = "distribution_management_system"
}
$candidateCredentials += [PSCustomObject]@{
    Source = "docker root defaults"
    User = "root"
    Password = "rootpassword"
    Name = "distribution_management_system"
}
$candidateCredentials += [PSCustomObject]@{
    Source = "local root password"
    User = "root"
    Password = "root"
    Name = "distribution_management_system"
}
$candidateCredentials += [PSCustomObject]@{
    Source = "local root no password"
    User = "root"
    Password = ""
    Name = "distribution_management_system"
}

# 4) Fallback from resolved values.
$candidateCredentials += [PSCustomObject]@{
    Source = "resolved fallback"
    User = $DbUser
    Password = $DbPassword
    Name = $DbName
}

$seen = @{}
$selected = $null
foreach ($candidate in $candidateCredentials) {
    $key = "$($candidate.User)|$($candidate.Password)|$($candidate.Name)"
    if ($seen.ContainsKey($key)) {
        continue
    }
    $seen[$key] = $true

    Write-Host "Testing MySQL credential source: $($candidate.Source) (user=$($candidate.User), db=$($candidate.Name))" -ForegroundColor DarkCyan
    if (Test-MySqlCredential -PythonExePath $pythonExe -DbHost $MySqlHost -Port $MySqlPort -User $candidate.User -Password $candidate.Password -Database $candidate.Name) {
        $selected = $candidate
        break
    }
}

if ($null -eq $selected) {
    Write-Host "Unable to authenticate to MySQL at ${MySqlHost}:$MySqlPort with known credential profiles." -ForegroundColor Red
    Write-Host "Run with explicit credentials, for example:" -ForegroundColor Yellow
    Write-Host "  .\start_manual.ps1 -DbUser root -DbPassword '<your-password>' -DbName distribution_management_system" -ForegroundColor Gray
    exit 1
}

$DbUser = $selected.User
$DbPassword = $selected.Password
$DbName = $selected.Name
Write-Host "Using MySQL credentials from: $($selected.Source)" -ForegroundColor Green

$apiBaseUrl = "http://localhost:$BackendPort/api"

$backendCommand = @"
`$host.UI.RawUI.WindowTitle = 'DMS Backend (Manual)'
Set-Location '$backendDir'
`$env:DB_HOST = '$MySqlHost'
`$env:DB_PORT = '$MySqlPort'
`$env:DB_USER = '$DbUser'
`$env:DB_PASSWORD = '$DbPassword'
`$env:DB_NAME = '$DbName'
`$env:HOST = '0.0.0.0'
`$env:PORT = '$BackendPort'
Write-Host "Starting backend on port $BackendPort (MySQL: ${MySqlHost}:$MySqlPort)..." -ForegroundColor Cyan
& '$pythonExe' -m uvicorn app.main:app --reload --host 0.0.0.0 --port $BackendPort
"@

$frontendCommand = @"
`$host.UI.RawUI.WindowTitle = 'DMS Frontend (Manual)'
Set-Location '$frontendDir'
`$env:VITE_API_URL = '$apiBaseUrl'
Write-Host 'Starting frontend on port $FrontendPort (API: $apiBaseUrl)...' -ForegroundColor Cyan
npm run dev -- --host 0.0.0.0 --port $FrontendPort
"@

Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand) | Out-Null
Start-Sleep -Seconds 1
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand) | Out-Null

Write-Host "Manual startup launched in separate terminals." -ForegroundColor Green
Write-Host "" 
Write-Host "Frontend:  http://localhost:$FrontendPort" -ForegroundColor White
Write-Host "Backend:   http://localhost:$BackendPort" -ForegroundColor White
Write-Host "API Docs:  http://localhost:$BackendPort/docs" -ForegroundColor White
Write-Host "MySQL:     ${MySqlHost}:$MySqlPort ($DbUser)" -ForegroundColor White
Write-Host "" 
Write-Host "Example with custom MySQL port:" -ForegroundColor Yellow
Write-Host "  .\start_manual.ps1 -MySqlPort 3307" -ForegroundColor Gray
Write-Host "Example with custom credentials:" -ForegroundColor Yellow
Write-Host "  .\start_manual.ps1 -DbUser root -DbPassword '' -DbName distribution_management_system" -ForegroundColor Gray