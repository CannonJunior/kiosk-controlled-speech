# Simple Windows Port Forwarding Setup for WSL Microphone Access
# Run this script in Windows PowerShell as Administrator

param(
    [Parameter(Mandatory=$false)]
    [string]$WSLHost = "172.18.95.41",
    
    [Parameter(Mandatory=$false)]
    [int]$Port = 8000
)

Write-Host "Setting up Windows Port Forwarding for WSL Microphone Access" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

Write-Host "Running as Administrator" -ForegroundColor Green

# Remove existing port forwarding rule if it exists
Write-Host "Removing any existing port forwarding rules..." -ForegroundColor Yellow
try {
    netsh interface portproxy delete v4tov4 listenport=${Port} listenaddress=127.0.0.1 2>$null
    Write-Host "Cleaned up existing rules" -ForegroundColor Green
} catch {
    Write-Host "No existing rules to clean up" -ForegroundColor Blue
}

# Add new port forwarding rule
Write-Host "Creating port forwarding rule..." -ForegroundColor Yellow
Write-Host "From: 127.0.0.1:${Port}" -ForegroundColor Blue
Write-Host "To:   ${WSLHost}:${Port}" -ForegroundColor Blue

try {
    $result = netsh interface portproxy add v4tov4 listenport=${Port} listenaddress=127.0.0.1 connectport=${Port} connectaddress=${WSLHost}
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Port forwarding rule created successfully!" -ForegroundColor Green
    } else {
        Write-Host "Failed to create port forwarding rule" -ForegroundColor Red
        Write-Host "Error: $result" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error creating port forwarding rule: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Verify the rule was created
Write-Host "Verifying port forwarding rules..." -ForegroundColor Yellow
$rules = netsh interface portproxy show v4tov4
Write-Host $rules

# Check Windows Firewall
Write-Host "Checking Windows Firewall..." -ForegroundColor Yellow
try {
    $firewallRule = Get-NetFirewallRule -DisplayName "*${Port}*" -ErrorAction SilentlyContinue
    if (-not $firewallRule) {
        Write-Host "Creating Windows Firewall rule for port ${Port}..." -ForegroundColor Yellow
        New-NetFirewallRule -DisplayName "WSL Kiosk Speech App" -Direction Inbound -Protocol TCP -LocalPort ${Port} -Action Allow
        Write-Host "Firewall rule created" -ForegroundColor Green
    } else {
        Write-Host "Firewall rule already exists" -ForegroundColor Green
    }
} catch {
    Write-Host "Could not configure firewall automatically" -ForegroundColor Yellow
    Write-Host "Manually allow port ${Port} in Windows Firewall if needed" -ForegroundColor Blue
}

Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "===============" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Blue
Write-Host "1. Make sure your WSL web app is running on ${WSLHost}:${Port}" -ForegroundColor White
Write-Host "2. Open your Windows browser to: http://localhost:${Port}" -ForegroundColor White
Write-Host "3. Test microphone access - it should work now!" -ForegroundColor White
Write-Host ""
Write-Host "Troubleshooting:" -ForegroundColor Blue
Write-Host "- Troubleshooting page: http://localhost:${Port}/troubleshooting" -ForegroundColor White
Write-Host "- To remove forwarding: netsh interface portproxy delete v4tov4 listenport=${Port} listenaddress=127.0.0.1" -ForegroundColor White
Write-Host ""
Write-Host "Your microphone should now work with the web application!" -ForegroundColor Green