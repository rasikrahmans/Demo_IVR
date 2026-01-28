"""
Clean interruption detection and buffer management
"""

import asyncio
import logging
import threading
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)

@dataclass
class CallState:
    """State for an active call"""
    ucid: str
    is_agent_speaking: bool = False
    is_interrupted: bool = False
    interruption_callback: Optional[Callable] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class InterruptionManager:
    """
    Clean, simple interruption detection and buffer management
    """
    
    def __init__(self):
        self._calls: Dict[str, CallState] = {}
        self._lock = threading.Lock()
        
    def start_call(self, ucid: str) -> CallState:
        """Start tracking a new call"""
        with self._lock:
            call_state = CallState(ucid=ucid)
            self._calls[ucid] = call_state
            log.info(f"🎯 Started tracking call: {ucid}")
            return call_state
    
    def end_call(self, ucid: str):
        """Stop tracking a call and cleanup"""
        with self._lock:
            if ucid in self._calls:
                del self._calls[ucid]
                log.info(f"🧹 Stopped tracking call: {ucid}")
    
    def set_agent_speaking(self, ucid: str, speaking: bool, reason: str = ""):
        """Set agent speaking state"""
        with self._lock:
            if ucid in self._calls:
                self._calls[ucid].is_agent_speaking = speaking
                status = "🎤 SPEAKING" if speaking else "🔇 SILENT"
                log.info(f"{status} - {ucid}: {reason}")
    
    def detect_interruption(self, ucid: str, transcript: str, confidence: float = 0.0) -> bool:
        """
        Detect if customer is interrupting agent speech
        Returns True if interruption detected
        """
        with self._lock:
            if ucid not in self._calls:
                return False
            
            call_state = self._calls[ucid]
            
            # Only detect interruption if agent is speaking
            if not call_state.is_agent_speaking:
                return False
            
            # Simple interruption detection based on transcript
            interruption_phrases = [
                "stop", "wait", "hold on", "excuse me", "sorry", 
                "let me", "actually", "but", "no", "yes"
            ]
            
            transcript_lower = transcript.lower().strip()
            
            # Check for interruption phrases
            is_interruption = any(phrase in transcript_lower for phrase in interruption_phrases)
            
            # Also consider any speech with decent confidence as potential interruption
            if confidence > 0.7 and len(transcript_lower) > 2:
                is_interruption = True
            
            if is_interruption:
                call_state.is_interrupted = True
                call_state.is_agent_speaking = False  # Stop agent speaking
                
                log.error(f"🛑 INTERRUPTION DETECTED - {ucid}: '{transcript}' (confidence: {confidence:.2f})")
                
                # Call interruption callback if set
                if call_state.interruption_callback:
                    try:
                        asyncio.create_task(call_state.interruption_callback())
                    except Exception as e:
                        log.error(f"Error in interruption callback: {e}")
                
                return True
            
            return False
    
    def is_interrupted(self, ucid: str) -> bool:
        """Check if call is currently interrupted"""
        with self._lock:
            if ucid in self._calls:
                return self._calls[ucid].is_interrupted
            return False
    
    def clear_interruption(self, ucid: str):
        """Clear interruption flag"""
        with self._lock:
            if ucid in self._calls:
                self._calls[ucid].is_interrupted = False
                log.info(f"🟢 Interruption cleared for {ucid}")
    
    def set_interruption_callback(self, ucid: str, callback: Callable):
        """Set callback to be called when interruption is detected"""
        with self._lock:
            if ucid in self._calls:
                self._calls[ucid].interruption_callback = callback
    
    def get_call_state(self, ucid: str) -> Optional[CallState]:
        """Get call state"""
        with self._lock:
            return self._calls.get(ucid)

# Global interruption manager instance
interruption_manager = InterruptionManager()