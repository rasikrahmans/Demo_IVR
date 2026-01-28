"""
Ozonetel integration service
Clean implementation for phone call handling
"""

import logging
import requests
from typing import Optional

from config import Config

log = logging.getLogger(__name__)

class OzonetelService:
    """
    Clean Ozonetel service for phone integration
    """
    
    def __init__(self):
        self.api_key = Config.OZONETEL_API_KEY
        self.caller_id = Config.OZONETEL_CALLER_ID
        self.sip_number = Config.OZONETEL_SIP_NUMBER
        
        self.base_url = "https://api1.cloudagent.in/cloudAgentRestAPI/index.php/CloudAgent"
        
        if not self.api_key:
            log.warning("⚠️ Ozonetel API key not configured")
        else:
            log.info("✅ Ozonetel service initialized")
    
    async def hangup_call(self, ucid: str, caller_phone: Optional[str] = None) -> bool:
        """
        Hangup a call via Ozonetel API
        
        Args:
            ucid: Unique call ID
            caller_phone: Caller's phone number (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.api_key:
                log.warning("Cannot hangup call - no Ozonetel API key")
                return False
            
            # Ozonetel hangup API endpoint
            hangup_url = f"{self.base_url}/hangupCall"
            
            params = {
                'api_key': self.api_key,
                'ucid': ucid
            }
            
            if caller_phone:
                params['phone'] = caller_phone
            
            log.info(f"🔌 Attempting to hangup call {ucid}")
            
            response = requests.get(hangup_url, params=params, timeout=10)
            
            if response.status_code == 200:
                log.info(f"✅ Successfully hung up call {ucid}")
                return True
            else:
                log.warning(f"⚠️ Hangup failed for {ucid}: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            log.error(f"❌ Error hanging up call {ucid}: {e}")
            return False
    
    async def stop_audio_playback(self, ucid: str) -> bool:
        """
        Stop audio playback for a call (if supported by Ozonetel)
        
        Args:
            ucid: Unique call ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.api_key:
                log.warning("Cannot stop audio - no Ozonetel API key")
                return False
            
            # Note: This is a placeholder - actual implementation depends on Ozonetel API
            # Some providers support stopping audio playback, others require call hangup
            
            log.info(f"🛑 Attempting to stop audio playback for {ucid}")
            
            # For now, we'll use hangup as the stop mechanism
            # In a real implementation, you might have a specific "stop audio" endpoint
            return await self.hangup_call(ucid)
            
        except Exception as e:
            log.error(f"❌ Error stopping audio for {ucid}: {e}")
            return False
    
    def get_webhook_response(self, ucid: str, caller_id: str) -> str:
        """
        Generate XML response for Ozonetel webhook
        
        Args:
            ucid: Unique call ID
            caller_id: Caller's phone number
            
        Returns:
            XML response string
        """
        try:
            # Use the exact WebSocket URL format that works
            ws_url = f'ws://43.205.216.106:8000/ws?ucid={ucid}&cid={caller_id}'
            
            # Generate XML response with exact format that should work
            response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<response>
    <start-record/>
    <stream is_sip='true' url='{ws_url}'>{self.sip_number}</stream>
</response>"""
            
            log.info(f"🔗 Generated webhook response for {ucid} -> {ws_url}")
            log.info(f"📋 XML Response (formatted):")
            log.info(f"   <?xml version=\"1.0\" encoding=\"UTF-8\"?>")
            log.info(f"   <response>")
            log.info(f"       <start-record/>")
            log.info(f"       <stream is_sip='true' url='{ws_url}'>{self.sip_number}</stream>")
            log.info(f"   </response>")
            log.info(f"🔧 SIP Number: {self.sip_number}")
            log.info(f"🌐 WebSocket URL: {ws_url}")
            
            return response_xml
            
        except Exception as e:
            log.error(f"❌ Error generating webhook response: {e}")
            return "<response></response>"