#!/usr/bin/env python3
"""
Simple WebSocket test to verify connectivity
Run this while your IVR server is running to test WebSocket connectivity
"""

import asyncio
import websockets
import json
import sys

async def test_websocket():
    """Test WebSocket connection"""
    
    # Your server details
    host = "43.205.216.106"
    port = "8000"
    
    # Test the exact URL that Ozonetel should be connecting to
    test_url = f"ws://{host}:{port}/ws?ucid=test123&cid=+1234567890"
    
    print(f"🔍 Testing WebSocket connection to: {test_url}")
    print("=" * 60)
    
    try:
        print("⏳ Attempting to connect...")
        
        # Connect with timeout
        websocket = await asyncio.wait_for(
            websockets.connect(test_url), 
            timeout=10.0
        )
        
        print("✅ CONNECTION SUCCESSFUL!")
        print(f"📡 Connected to: {test_url}")
        
        # Send a start event like Ozonetel would
        start_message = {
            "event": "start",
            "ucid": "test123",
            "cid": "+1234567890"
        }
        
        await websocket.send(json.dumps(start_message))
        print("📤 Sent start event")
        
        # Try to receive response
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"📥 Received: {response}")
        except asyncio.TimeoutError:
            print("⏰ No response received (this might be normal)")
        
        # Send some test audio data
        audio_message = {
            "type": "media",
            "data": {
                "samples": [100, 200, 150, 300] * 20  # Fake audio samples
            }
        }
        
        await websocket.send(json.dumps(audio_message))
        print("📤 Sent test audio data")
        
        # Keep connection alive for a few seconds
        print("🔄 Keeping connection alive for 10 seconds...")
        await asyncio.sleep(10)
        
        # Send stop event
        stop_message = {
            "event": "stop",
            "ucid": "test123"
        }
        
        await websocket.send(json.dumps(stop_message))
        print("📤 Sent stop event")
        
        await websocket.close()
        print("✅ Test completed successfully!")
        
        return True
        
    except asyncio.TimeoutError:
        print("❌ CONNECTION TIMEOUT - Server may not be running or accessible")
        return False
    except ConnectionRefusedError:
        print("❌ CONNECTION REFUSED - Server is not running on this port")
        return False
    except Exception as e:
        print(f"❌ CONNECTION FAILED: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Simple WebSocket Connection Test")
    print("=" * 60)
    print("Make sure your IVR server is running first!")
    print("Run: python3 main.py")
    print("=" * 60)
    
    try:
        result = asyncio.run(test_websocket())
        if result:
            print("\n🎉 SUCCESS: WebSocket is working correctly!")
            print("If Ozonetel still can't connect, the issue is network/firewall related")
        else:
            print("\n❌ FAILED: WebSocket is not accessible")
            print("Check if your server is running and port 8000 is open")
            
    except KeyboardInterrupt:
        print("\n👋 Test interrupted")
    except Exception as e:
        print(f"\n❌ Test error: {e}")