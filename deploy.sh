#!/bin/bash

# Demo Bot IVR Deployment Script
# Clean deployment with Sarvam STT/TTS and interruption handling

echo "🚀 Deploying Demo Bot IVR..."

# Stop any existing processes
echo "🛑 Stopping existing processes..."
pkill -f "python.*main.py" || true
pkill -f "uvicorn" || true

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Check configuration
echo "🔧 Checking configuration..."
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Validate required environment variables
source .env
if [ -z "$SARVAM_API_KEY" ] || [ -z "$OZONETEL_API_KEY" ] || [ -z "$WEBHOOK_ENDPOINT" ]; then
    echo "❌ Error: Missing required configuration!"
    echo "Please check SARVAM_API_KEY, OZONETEL_API_KEY, and WEBHOOK_ENDPOINT in .env"
    exit 1
fi

echo "✅ Configuration validated"

# Start the server
echo "🎯 Starting Demo Bot IVR server..."
echo "📞 Webhook endpoint: http://$WEBHOOK_ENDPOINT/hook"
echo "🎙️ WebSocket endpoint: ws://$WEBHOOK_ENDPOINT/ws"

# Run in background with logging
nohup python main.py > demo_bot_ivr.log 2>&1 &
SERVER_PID=$!

echo "✅ Demo Bot IVR started with PID: $SERVER_PID"
echo "📋 Log file: demo_bot_ivr.log"
echo "🔍 Monitor logs: tail -f demo_bot_ivr.log"

# Wait a moment and check if server started successfully
sleep 3
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ Server is running successfully!"
    echo "🌐 Health check: curl http://localhost:8000/health"
else
    echo "❌ Server failed to start. Check demo_bot_ivr.log for errors."
    exit 1
fi