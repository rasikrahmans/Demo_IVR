"""
Ozonetel Service for Parcel Tracking Agent
Handles call termination and control via Ozonetel API
"""

import os
import logging
import requests
from typing import Dict, Optional

log = logging.getLogger(__name__)

class OzonetelService:
    """Service for Ozonetel call control operations"""
    
    def __init__(self):
        self.api_key = os.getenv('OZONETEL_API_KEY')
        self.caller_id = os.getenv('OZONETEL_CALLER_ID', '917971142165')
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            log.warning("Ozonetel API key not configured - call control will be simulated")
        else:
            log.info(f"Ozonetel service initialized - API Key: {self.api_key[:10]}...")
    
    async def hangup_call(self, call_id: str, phone_number: str = None, did: str = None) -> bool:
        """Terminate active call via Ozonetel V1 API
        
        Args:
            call_id: Call ID to terminate (UCID from Ozonetel)
            phone_number: Customer phone number (optional)
            did: DID number (optional, will use default from settings)
            
        Returns:
            Success status
        """
        if not self.enabled:
            log.info(f"Simulating call hangup: {call_id}")
            return True
        
        # Use default DID if not provided
        if not did:
            did = os.getenv('OZONETEL_DID', self.caller_id)
        
        try:
            # Use the V1 API endpoint for call termination
            hangup_url = "https://in1-ccaas-api.ozonetel.com/api/v1/CallControl/Disconnect"
            
            params = {
                'ucid': call_id,
                'api_key': self.api_key,
                'did': did
            }
            
            # Add phone number if provided
            if phone_number:
                # Format phone number (remove any prefixes)
                clean_phone = ''.join(filter(str.isdigit, phone_number))
                if clean_phone.startswith('91'):
                    clean_phone = clean_phone[2:]  # Remove country code
                if clean_phone.startswith('0'):
                    clean_phone = clean_phone[1:]  # Remove leading 0
                params['phoneno'] = clean_phone
            
            log.info(f"🛑 Attempting to drop call - UCID: {call_id}, Phone: {phone_number}, DID: {did}")
            
            response = requests.get(hangup_url, params=params, timeout=10)
            
            log.info(f"📊 Drop Status: {response.status_code}")
            log.info(f"📄 Drop Response: {response.text}")
            
            # Parse response
            result_json = {}
            try:
                result_json = response.json()
            except:
                pass
            
            success = False
            message = ""
            
            if result_json.get("status") == "success" or "success" in response.text.lower():
                success = True
                message = "✅ CALL DROPPED SUCCESSFULLY!"
            else:
                message = "⚠️ CALL NOT FOUND (normal if call ended)"
            
            log.info(message)
            return success
            
        except Exception as e:
            log.error(f"❌ Error dropping call: {e}")
            return False
    
    async def stop_audio_playback(self, call_id: str) -> bool:
        """Stop current audio playback immediately (for interruption handling)
        
        Args:
            call_id: Active call ID
            
        Returns:
            Success status
        """
        if not self.enabled:
            log.info(f"Simulating audio stop: {call_id}")
            return True
        
        try:
            # Use Ozonetel call control API to stop/mute current audio
            mute_url = "https://in1-ccaas-api.ozonetel.com/api/v1/CallControl/Mute"
            
            params = {
                'ucid': call_id,
                'api_key': self.api_key
            }
            
            log.info(f"🔇 Attempting to stop audio playback for call {call_id}")
            
            response = requests.get(mute_url, params=params, timeout=5)
            
            if response.status_code == 200:
                log.info(f"✅ Audio playback stopped for call {call_id}")
                return True
            else:
                log.warning(f"⚠️ Mute failed ({response.status_code})")
                return False
                
        except Exception as e:
            log.error(f"❌ Error stopping audio playback: {e}")
            return False
    
    def is_enabled(self) -> bool:
        """Check if Ozonetel service is enabled"""
        return self.enabled