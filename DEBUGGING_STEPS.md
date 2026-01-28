# IVR Call Disconnection Debugging Guide

## Current Issue
Calls are disconnecting after 1 second. The WebSocket endpoint is never being hit by Ozonetel, even though the XML response is generated correctly.

## Key Changes Made

### 1. Enhanced WebSocket Handler (`api/webhook.py`)
- Added detailed logging to track WebSocket connections
- Restored full conversation flow with STT/TTS integration
- Fixed method signatures to match available services
- Added proper error handling and cleanup

### 2. Improved XML Response (`services/ozonetel.py`)
- Enhanced logging to show exact XML format being sent
- Using correct SIP number from configuration
- Verified WebSocket URL format matches working version

### 3. Enhanced Main Application (`main.py`)
- Added detailed WebSocket connection logging
- Added test endpoints for connectivity verification
- Enhanced debugging information

### 4. Fixed Service Compatibility (`services/sarvam_stt.py`)
- Added compatibility method for audio processing
- Ensured proper method signatures

## Debugging Steps

### Step 1: Test WebSocket Connectivity
```bash
# While your server is running, test WebSocket connectivity:
python3 test_websocket_simple.py
```

### Step 2: Check Server Logs
Look for these log messages when making a test call:
1. `📞 Inbound call - Event: NewCall` ✅ (Working)
2. `🔗 Generated webhook response` ✅ (Working)  
3. `🚨 WEBSOCKET ENDPOINT HIT!` ❌ (Missing - This is the problem!)

### Step 3: Test HTTP Connectivity
```bash
# Test if server is accessible externally:
curl http://43.205.216.106:8000/test-connection
```

### Step 4: Advanced WebSocket Testing
```bash
# Run comprehensive WebSocket tests:
python3 debug_websocket.py
```

## Possible Root Causes

### 1. Network/Firewall Issues
- Ozonetel's servers cannot reach your WebSocket endpoint
- Port 8000 might be blocked for WebSocket connections (even if HTTP works)
- AWS security groups might be blocking WebSocket upgrades

### 2. WebSocket Protocol Issues
- Ozonetel might expect specific WebSocket subprotocols
- Connection upgrade headers might be missing
- WebSocket handshake might be failing

### 3. XML Response Format
- Ozonetel might expect different XML structure
- URL encoding issues in the WebSocket URL
- SIP number format might be incorrect

## Next Steps

### Immediate Actions:
1. **Run the test script** while server is running to verify WebSocket works locally
2. **Check AWS security groups** - ensure WebSocket connections are allowed
3. **Test from external source** - try connecting to WebSocket from outside AWS

### If WebSocket Test Passes:
The issue is likely that Ozonetel cannot reach your server. Check:
- AWS security group rules
- Network ACLs
- Firewall settings
- Whether Ozonetel needs to whitelist your IP

### If WebSocket Test Fails:
The issue is with the WebSocket implementation. Check:
- Server configuration
- Port binding
- WebSocket library compatibility

## Expected Log Output (When Working)

```
INFO:api.webhook:📞 Inbound call - Event: NewCall, UCID: 12345, Caller: +1234567890
INFO:services.ozonetel:🔗 Generated webhook response for 12345 -> ws://43.205.216.106:8000/ws?ucid=12345&cid=+1234567890
INFO:api.webhook:🔗 Connecting call 12345 to WebSocket
INFO:main:🚨 WEBSOCKET ENDPOINT HIT! UCID: 12345, CID: +1234567890  <-- THIS IS MISSING!
INFO:main:🔍 WebSocket connection details:
INFO:api.webhook:✅ WebSocket accepted successfully - UCID: 12345
```

## Contact Points
- If WebSocket test passes but Ozonetel still can't connect → Network/firewall issue
- If WebSocket test fails → Server configuration issue
- If logs show WebSocket hit but call still drops → Application logic issue