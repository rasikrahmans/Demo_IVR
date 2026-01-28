#!/usr/bin/env python3
"""
Quick WebSocket debugging script for IVR system
"""

import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def test_websocket_connection():
    """Test WebSocket connection to your IVR system"""
    
    # Your server details
    host = "43.205.216.106"
    port = "8000"
    
    # Test URLs
    test_urls = [
        f"ws://{host}:{port}/ws",
        f"ws://{host}:{port}/ws?ucid=test123&cid=+1234567890"
    ]
    
    for url in test_urls:
        log.info(f"🔍 Testing WebSocket connection to: {url}")
        
        try:
            async with websockets.connect(url) as websocket:
                log.info(f"✅ Successfully connected to {url}")
                
                # Send a test message
                test_message = {
                    "type": "test",
                    "message": "Hello from debug script"
                }
                
                await websocket.send(json.dumps(test_message))
                log.info("📤 Sent test message")
                
                # Try to receive a response (with timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    log.info(f"📥 Received response: {response}")
                except asyncio.TimeoutError:
                    log.info("⏰ No response received (this is normal for IVR)")
                
                log.info(f"✅ WebSocket test completed for {url}")
                
        except Exception as e:
            log.error(f"❌ Failed to connect to {url}: {e}")
        
        print("-" * 50)

if __name__ == "__main__":
    print("🧪 WebSocket Connection Tester for IVR System")
    print("=" * 50)
    
    try:
        asyncio.run(test_websocket_connection())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")