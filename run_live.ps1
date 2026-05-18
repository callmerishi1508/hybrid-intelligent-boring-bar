# run_live.ps1 - Example: Set up Azure credentials and run live Digital Twin integration
# 
# Usage:
#   .\run_live.ps1 -mode test    # Dry-run test (safe, local only)
#   .\run_live.ps1 -mode check   # Check credentials without sending data
#   .\run_live.ps1 -mode live    # Live update to Azure (requires valid credentials)

param(
    [string]$mode = "test",
    [int]$maxRows = 50,
    [float]$speed = 1.0
)

Write-Host "Azure Digital Twin Live Integration Runner" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check Python
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) {
    Write-Host "ERROR: Python not found. Please install Python and ensure it is in PATH." -ForegroundColor Red
    exit 1
}

Write-Host "Python: $($python.Source)" -ForegroundColor Green

# Set environment variables (UPDATE THESE WITH YOUR VALUES)
Write-Host "`nSetting up environment variables..." -ForegroundColor Yellow

# Azure Digital Twins endpoint - REQUIRED
$env:ADT_ENDPOINT = "https://project7-digitaltwin.api.wus2.digitaltwins.azure.net"

# Service Principal credentials - REQUIRED for live mode
$env:ADT_TENANT_ID = ""          # TODO: Replace with your tenant ID
$env:ADT_CLIENT_ID = ""          # TODO: Replace with your service principal client ID
$env:ADT_CLIENT_SECRET = ""      # TODO: Replace with your service principal secret

# Twin ID to update - REQUIRED
$env:DIGITAL_TWIN_ID = "BoringBar_01"

# IoT Hub device connection string - OPTIONAL (telemetry publishing)
$env:IOTHUB_DEVICE_CONNECTION_STRING = ""  # TODO: Replace with device connection string

# Simulation speed
$env:SIMULATION_SPEED_FACTOR = $speed.ToString()

# Logging level
$env:LOG_LEVEL = "INFO"

Write-Host "ADT_ENDPOINT: $env:ADT_ENDPOINT" -ForegroundColor Gray
Write-Host "DIGITAL_TWIN_ID: $env:DIGITAL_TWIN_ID" -ForegroundColor Gray
Write-Host "SIMULATION_SPEED_FACTOR: $env:SIMULATION_SPEED_FACTOR" -ForegroundColor Gray

# Handle run mode
switch ($mode.ToLower()) {
    "test" {
        Write-Host "`nRunning DRY-RUN mode (local only, no Azure calls)..." -ForegroundColor Cyan
        Write-Host "Command: python main.py --dry-run --max-rows $maxRows" -ForegroundColor Gray
        & python main.py --dry-run --max-rows $maxRows
    }
    "check" {
        Write-Host "`nVerifying credentials..." -ForegroundColor Cyan
        Write-Host "Command: python -c 'from config import ensure_live_credentials; success, msg = ensure_live_credentials(); print(\"OK\" if success else f\"FAIL: {msg}\")'" -ForegroundColor Gray
        & python -c "from config import ensure_live_credentials; success, msg = ensure_live_credentials(); print('OK' if success else f'FAIL: {msg}')"
    }
    "live" {
        Write-Host "`nPrep: Verify all ADT_* and DIGITAL_TWIN_ID environment variables are set above." -ForegroundColor Yellow
        Write-Host "Press ENTER to continue with LIVE mode, or Ctrl+C to cancel..." -ForegroundColor Yellow
        Read-Host "Ready?"
        
        Write-Host "`nRunning LIVE mode (real Azure updates)..." -ForegroundColor Cyan
        Write-Host "Command: python main.py --live --max-rows $maxRows --speed $speed" -ForegroundColor Gray
        Write-Host "This will send telemetry and update properties in Azure Digital Twin Explorer." -ForegroundColor Cyan
        & python main.py --live --max-rows $maxRows --speed $speed
    }
    default {
        Write-Host "Unknown mode: $mode" -ForegroundColor Red
        Write-Host "Valid modes: test, check, live" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "`nDone." -ForegroundColor Green
