#!/bin/bash

echo "Setting up WSL environment for Kiosk Controlled Speech..."

# Update package lists
sudo apt update

# Install Python development tools
sudo apt install -y python3-pip python3-venv python3-dev

# Install audio libraries
sudo apt install -y portaudio19-dev python3-pyaudio alsa-utils pulseaudio

# Install computer vision libraries
sudo apt install -y libopencv-dev python3-opencv

# Install GUI libraries for Windows interop
sudo apt install -y x11-apps

# Install system dependencies
sudo apt install -y build-essential cmake pkg-config

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -e .
pip install -e ".[dev]"

# Create logs directory
mkdir -p logs

# Set up audio permissions
sudo usermod -a -G audio $USER

# Configure PulseAudio for WSL
echo "Configuring PulseAudio for WSL..."
cat >> ~/.bashrc << 'EOF'

# PulseAudio configuration for WSL
export PULSE_RUNTIME_PATH="/mnt/wslg/runtime/PulseAudio"
export PULSE_COOKIE="/mnt/wslg/runtime/PulseAudio/auth.cookie"

# Display configuration for GUI apps
export DISPLAY=:0

# Activate virtual environment
source ~/src/kiosk-controlled-speech/venv/bin/activate
EOF

echo "WSL setup complete!"
echo "Please restart your terminal or run: source ~/.bashrc"
echo "Then test audio with: python -c \"import sounddevice; print(sounddevice.query_devices())\""