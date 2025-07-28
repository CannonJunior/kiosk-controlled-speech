#!/bin/bash
# Kiosk Speech Web Application Startup Script
# Configures WSL networking and starts the web application

set -e

echo "🚀 Starting Kiosk Speech Web Application"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if we're in WSL
if [[ ! $(uname -r) =~ microsoft ]]; then
    print_warning "This script is designed for WSL environments"
fi

# Get WSL IP address
WSL_IP=$(hostname -I | awk '{print $1}')
print_info "WSL IP Address: $WSL_IP"

# Check if port 8000 is available
if netstat -tulpn 2>/dev/null | grep -q ":8000 "; then
    print_error "Port 8000 is already in use. Please stop the existing service."
    exit 1
fi

# Create necessary directories
print_status "Creating directories..."
mkdir -p /tmp/web_audio
mkdir -p logs

# Check Python environment
print_status "Checking Python environment..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

# Check for virtual environment
VENV_PATH="venv"
if [ ! -d "$VENV_PATH" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Check required packages
print_status "Checking dependencies..."
python3 -c "import fastapi, uvicorn, fastmcp" 2>/dev/null || {
    print_warning "Installing required packages..."
    pip install fastapi uvicorn fastmcp websockets
}

# Start the web application
print_status "Starting web application..."
print_info "Web interface will be available at:"
print_info "  Local (WSL):     http://localhost:8000"
print_info "  Windows Host:    http://$WSL_IP:8000"
print_info ""
print_info "Press Ctrl+C to stop the server"
print_info ""

# Configure Windows firewall (instructions)
cat << EOF
${YELLOW}Windows Firewall Configuration:${NC}
If you can't access the interface from Windows, run this in PowerShell as Administrator:
  New-NetFirewallRule -DisplayName "WSL Port 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

${YELLOW}Alternative access methods:${NC}
1. Use WSL IP directly: http://$WSL_IP:8000
2. Set up port forwarding: netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$WSL_IP

EOF

# Start the server
export PYTHONPATH="$(pwd):$PYTHONPATH"
cd "$(dirname "$0")"

# Ensure virtual environment is still active
source "$VENV_PATH/bin/activate"

# Run with uvicorn directly for better control
python3 -m uvicorn web_app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --access-log \
    --reload