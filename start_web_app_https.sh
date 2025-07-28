#!/bin/bash
# HTTPS version of the web application startup script
# Generates self-signed certificates for local HTTPS access

set -e

echo "🔒 Starting Kiosk Speech Web Application (HTTPS)"
echo "==============================================="

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

# Check if we're in WSL
if [[ ! $(uname -r) =~ microsoft ]]; then
    print_warning "This script is designed for WSL environments"
fi

# Get WSL IP address
WSL_IP=$(hostname -I | awk '{print $1}')
print_info "WSL IP Address: $WSL_IP"

# Create certificates directory
CERT_DIR="certs"
mkdir -p "$CERT_DIR"

# Generate self-signed certificate if it doesn't exist
if [ ! -f "$CERT_DIR/cert.pem" ] || [ ! -f "$CERT_DIR/key.pem" ]; then
    print_status "Generating self-signed SSL certificate..."
    
    # Create OpenSSL config for SAN (Subject Alternative Names)
    cat > "$CERT_DIR/openssl.conf" << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = US
ST = Development
L = Local
O = Kiosk Speech App
CN = localhost

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
IP.1 = 127.0.0.1
IP.2 = $WSL_IP
EOF

    # Generate private key and certificate
    openssl req -x509 -newkey rsa:2048 -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" \
        -days 365 -nodes -config "$CERT_DIR/openssl.conf" -extensions v3_req
    
    print_status "SSL certificate generated"
else
    print_status "Using existing SSL certificate"
fi

# Check for virtual environment
VENV_PATH="venv"
if [ ! -d "$VENV_PATH" ]; then
    print_error "Virtual environment not found. Please run ./setup_web_app.sh first"
    exit 1
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Check if port 8443 is available (HTTPS port)
if netstat -tulpn 2>/dev/null | grep -q ":8443 "; then
    print_error "Port 8443 is already in use. Please stop the existing service."
    exit 1
fi

# Create necessary directories
print_status "Creating directories..."
mkdir -p /tmp/web_audio
mkdir -p logs

print_status "Starting HTTPS web application..."
print_info "Web interface will be available at:"
print_info "  Local (WSL):     https://localhost:8443"
print_info "  Windows Host:    https://$WSL_IP:8443"
print_info ""
print_warning "⚠️  You will see a security warning because of the self-signed certificate."
print_warning "   Click 'Advanced' and 'Proceed to localhost' (or similar) to continue."
print_info ""
print_info "Press Ctrl+C to stop the server"
print_info ""

# Configure Windows firewall (instructions)
cat << EOF
${YELLOW}Windows Firewall Configuration:${NC}
If you can't access the interface from Windows, run this in PowerShell as Administrator:
  New-NetFirewallRule -DisplayName "WSL HTTPS Port 8443" -Direction Inbound -LocalPort 8443 -Protocol TCP -Action Allow

${YELLOW}Alternative access methods:${NC}
1. Use WSL IP directly: https://$WSL_IP:8443
2. Set up port forwarding: netsh interface portproxy add v4tov4 listenport=8443 listenaddress=0.0.0.0 connectport=8443 connectaddress=$WSL_IP

EOF

# Start the server with HTTPS
export PYTHONPATH="$(pwd):$PYTHONPATH"
cd "$(dirname "$0")"

# Ensure virtual environment is still active
source "$VENV_PATH/bin/activate"

# Run with uvicorn with SSL
python3 -m uvicorn web_app.main:app \
    --host 0.0.0.0 \
    --port 8443 \
    --ssl-keyfile "$(pwd)/$CERT_DIR/key.pem" \
    --ssl-certfile "$(pwd)/$CERT_DIR/cert.pem" \
    --log-level info \
    --access-log