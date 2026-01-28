#!/usr/bin/env python3
"""
Quick WebSocket debugging script for IVR system
Tests both internal and external connectivity
"""

import asyncio
import websockets
import json
import logging
import requests

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def test_websocket_connection():
    """Test WebSocket connection to your IVR system"""
    
    # Your server details
    host = "43.205.216.106"
    port = "8000"
    
    # First test HTTP connectivity
    log.info("🌐 Testing HTTP connectivity first...")
    try:
        response = requests.get(f"http://{host}:{port}/test-connection", timeout=10)
        if response.status_code == 200:
            log.info("✅ HTTP connection successful")
            log.info(f"📋 Server response: {response.json()}")
        else:
            log.error(f"❌ HTTP connection failed: {response.status_code}")
    except Exception as e:
        log.error(f"❌ HTTP connection failed: {e}")
    
    print("-" * 50)
    
    # Test WebSocket URLs
    test_urls = [
        f"ws://{host}:{port}/ws",
        f"ws://{host}:{port}/ws?ucid=test123&cid=+1234567890",
        f"ws://{host}:{port}/ws?ucid=22769607058426118&cid=+918524945114"  # Use actual call ID from logs
    ]
    
    for url in test_urls:
        log.info(f"🔍 Testing WebSocket connection to: {url}")
        
        try:
            # Try to connect with a longer timeout
            async with websockets.connect(url, timeout=15) as websocket:
                log.info(f"✅ Successfully connected to {url}")
                
                # Send a test message
                test_message = {
                    "type": "test",
                    "message": "Hello from debug script",
                    "timestamp": "2026-01-28T19:00:00Z"
                }
                
                await websocket.send(json.dumps(test_message))
                log.info("📤 Sent test message")
                
                # Try to receive a response (with timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    log.info(f"📥 Received response: {response}")
                except asyncio.TimeoutError:
                    log.info("⏰ No response received within 10 seconds (this might be normal)")
                
                # Send a ping to test connection
                try:
                    await websocket.ping()
                    log.info("🏓 Ping successful")
                except Exception as e:
                    log.warning(f"⚠️ Ping failed: {e}")
                
                log.info(f"✅ WebSocket test completed successfully for {url}")
                
        except websockets.exceptions.ConnectionClosed as e:
            log.error(f"❌ WebSocket connection closed: {e}")
        except websockets.exceptions.InvalidURI as e:
            log.error(f"❌ Invalid WebSocket URI: {e}")
        except asyncio.TimeoutError:
            log.error(f"❌ Connection timeout for {url}")
        except Exception as e:
            log.error(f"❌ Failed to connect to {url}: {e}")
        
        print("-" * 30)

async def test_ozonetel_simulation():
    """Simulate what Ozonetel might be doing"""
    host = "43.205.216.106"
    port = "8000"
    
    log.info("🤖 Simulating Ozonetel WebSocket connection...")
    
    # Use the exact URL format from the XML response
    ws_url = f"ws://{host}:{port}/ws?ucid=22769607058426118&cid=+918524945114"
    
    try:
        async with websockets.connect(ws_url, timeout=20) as websocket:
            log.info("✅ Ozonetel simulation: Connected successfully!")
            
            # Simulate Ozonetel sending start event
            start_event = {
                "event": "start",
                "ucid": "22769607058426118",
                "cid": "+918524945114"
            }
            
            await websocket.send(json.dumps(start_event))
            log.info("📤 Sent start event")
            
            # Wait for server response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                log.info(f"📥 Server responded: {response}")
            except asyncio.TimeoutError:
                log.info("⏰ No immediate response (this might be normal)")
            
            # Keep connection alive for a bit
            log.info("🔄 Keeping connection alive for 30 seconds...")
            await asyncio.sleep(30)
            
            log.info("✅ Ozonetel simulation completed successfully")
            
    except Exception as e:
        log.error(f"❌ Ozonetel simulation failed: {e}")

if __name__ == "__main__":
    print("🧪 WebSocket Connection Tester for IVR System")
    print("=" * 60)
    
    try:
        # Test basic connectivity
        asyncio.run(test_websocket_connection())
        
        print("\n" + "=" * 60)
        print("🤖 OZONETEL SIMULATION TEST")
        print("=" * 60)
        
        # Test Ozonetel simulation
        asyncio.run(test_ozonetel_simulation())
        
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")