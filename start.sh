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

# Check if port 8000 is in use and kill the process if found
print_info "Checking port 8000..."
if lsof -ti:8000 >/dev/null 2>&1; then
    print_warning "Process found running on port 8000, killing it..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || print_warning "Failed to kill process on port 8000"
    sleep 2
    if lsof -ti:8000 >/dev/null 2>&1; then
        echo "❌ Failed to free port 8000. Please manually kill the process and try again."
        exit 1
    else
        print_status "Port 8000 is now available"
    fi
else
    print_status "Port 8000 is available"
fi

print_status "Preloading Ollama model with 1 hour keep-alive..."
if command -v ollama >/dev/null 2>&1; then
    ollama run qwen2.5:1.5b --keepalive 3600 >/dev/null 2>&1 &
    print_status "Ollama model qwen2.5:1.5b loaded with 1 hour keep-alive"
else
    print_warning "Ollama not found in PATH, skipping model preload"
fi

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