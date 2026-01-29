#!/bin/bash

# Install Dependencies for Demo IVR System
# Run this script on the server after pulling from git

echo "🚀 Installing Demo IVR Dependencies..."

# Upgrade pip first
python3 -m pip install --upgrade pip

# Install all requirements
echo "📦 Installing Python packages..."
pip3 install -r requirements.txt

# Verify critical packages are installed
echo "✅ Verifying installations..."

# Check Sarvam AI (critical for STT)
python3 -c "import sarvamai; print('✅ sarvamai installed successfully')" || echo "❌ sarvamai installation failed"

# Check FastAPI
python3 -c "import fastapi; print('✅ fastapi installed successfully')" || echo "❌ fastapi installation failed"

# Check other critical packages
python3 -c "import websockets; print('✅ websockets installed successfully')" || echo "❌ websockets installation failed"
python3 -c "import requests; print('✅ requests installed successfully')" || echo "❌ requests installation failed"
python3 -c "import boto3; print('✅ boto3 installed successfully')" || echo "❌ boto3 installation failed"

echo "🎯 Installation complete! You can now run: python3 main.py"