#!/bin/bash
# Setup script for Kiosk Speech Web Application
# Creates virtual environment and installs dependencies

set -e

echo "🔧 Setting up Kiosk Speech Web Application"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

print_status "Python 3 found: $(python3 --version)"

# Create virtual environment
VENV_PATH="venv"
if [ -d "$VENV_PATH" ]; then
    print_warning "Virtual environment already exists"
else
    print_status "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install web application dependencies
print_status "Installing web application dependencies..."
pip install fastapi uvicorn websockets

# Install MCP dependencies
print_status "Installing MCP dependencies..."
pip install fastmcp

# Install additional dependencies for the existing project
print_status "Installing additional project dependencies..."
pip install faster-whisper sounddevice numpy httpx aiofiles

# Install optional development dependencies
print_warning "Installing optional development dependencies..."
pip install pytest pytest-asyncio || echo "Optional dev dependencies skipped"

# Create necessary directories
print_status "Creating directories..."
mkdir -p web_app/static
mkdir -p logs
mkdir -p /tmp/web_audio

print_status "Setup complete!"
print_info ""
print_info "To start the web application, run:"
print_info "  ./start_web_app.sh"
print_info ""
print_info "Or activate the virtual environment manually:"
print_info "  source venv/bin/activate"
print_info "  python -m uvicorn web_app.main:app --host 0.0.0.0 --port 8000"
print_info ""
print_info "Web interface will be available at:"
WSL_IP=$(hostname -I | awk '{print $1}')
print_info "  Local (WSL):     http://localhost:8000"
print_info "  Windows Host:    http://$WSL_IP:8000"