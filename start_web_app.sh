#!/bin/bash
# Simple web application startup with microphone access solutions

set -e

echo "🎤 Starting Kiosk Speech Web Application (Simple Setup)"
echo "===================================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Get WSL IP address
WSL_IP=$(hostname -I | awk '{print $1}')

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    print_status "Virtual environment activated"
else
    echo "❌ Virtual environment not found. Run ./setup_web_app.sh first"
    exit 1
fi

# Set Python path
export PYTHONPATH="$(pwd):$PYTHONPATH"

print_status "Starting web application on port 8000..."

print_info ""
print_info "🌐 Access Options for Microphone:"
print_info "================================"
print_info "✅ BEST: http://localhost:8000 (works in any browser)"
print_info "✅ ALT:  http://127.0.0.1:8000 (works in any browser)"
print_info "⚠️  IP:   http://$WSL_IP:8000 (may need browser config)"
print_info ""
print_warning "📝 If microphone doesn't work with IP access:"
print_warning "   1. Use localhost URL above, OR"
print_warning "   2. Configure Chrome: chrome://flags/#unsafely-treat-insecure-origin-as-secure"
print_warning "      Add: http://$WSL_IP:8000 and restart Chrome"
print_info ""
print_info "🛠️  Troubleshooting: Visit /troubleshooting for detailed help"
print_info "Press Ctrl+C to stop the server"
print_info ""

# Start the server
python3 -m uvicorn web_app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --access-log