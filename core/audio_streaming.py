"""
Audio streaming with interruption support
"""

import asyncio
import json
import logging
import time
from typing import Optional

from core.interruption import interruption_manager

log = logging.getLogger(__name__)

class AudioStreamer:
    """
    Clean audio streaming with interruption detection
    """
    
    @staticmethod
    async def stream_audio_with_interruption(websocket, audio_data: bytes, ucid: str) -> bool:
        """
        Stream audio to Ozonetel with interruption checking
        
        Args:
            websocket: WebSocket connection to Ozonetel
            audio_data: Raw audio bytes to stream
            ucid: Unique call ID
            
        Returns:
            True if completed successfully, False if interrupted
        """
        try:
            if not audio_data:
                log.warning(f"No audio data to stream for {ucid}")
                return False
            
            # Remove WAV header if present (first 44 bytes)
            if len(audio_data) > 44 and audio_data[:4] == b'RIFF':
                raw_audio = audio_data[44:]
            else:
                raw_audio = audio_data
            
            # Use optimal chunk size for quality vs responsiveness balance
            CHUNK_SIZE = 3200  # 100ms chunks at 16kHz (1600 samples * 2 bytes)
            
            total_chunks = (len(raw_audio) + CHUNK_SIZE - 1) // CHUNK_SIZE
            sent_chunks = 0
            
            log.info(f"🎵 Streaming {len(raw_audio)} bytes in {total_chunks} chunks for {ucid}")
            
            # Set agent speaking state
            interruption_manager.set_agent_speaking(ucid, True, "audio_streaming_started")
            
            for i in range(0, len(raw_audio), CHUNK_SIZE):
                # CRITICAL: Check for interruption before each chunk
                if interruption_manager.is_interrupted(ucid):
                    log.error(f"🛑 INTERRUPTION - Stopping audio stream at chunk {sent_chunks+1}/{total_chunks}")
                    return False
                
                chunk = raw_audio[i:i + CHUNK_SIZE]
                
                # Create Ozonetel audio message
                audio_message = {
                    "type": "audio",
                    "ucid": ucid,
                    "data": list(chunk),
                    "timestamp": time.time()
                }
                
                try:
                    await websocket.send(json.dumps(audio_message))
                    sent_chunks += 1
                    
                    # Small delay for interruption responsiveness
                    await asyncio.sleep(0.005)  # 5ms delay
                    
                except Exception as e:
                    log.error(f"Error sending audio chunk {sent_chunks+1}: {e}")
                    return False
            
            log.info(f"✅ Audio streaming completed: {sent_chunks}/{total_chunks} chunks for {ucid}")
            return True
            
        except Exception as e:
            log.error(f"❌ Error in audio streaming for {ucid}: {e}")
            return False
        finally:
            # Always clear agent speaking state when done
            interruption_manager.set_agent_speaking(ucid, False, "audio_streaming_finished")
    
    @staticmethod
    async def emergency_stop_audio(ucid: str):
        """
        Emergency stop all audio for a call
        """
        try:
            log.info(f"🚨 EMERGENCY STOP: Cancelling all audio for {ucid}")
            
            # Stop agent speaking immediately
            interruption_manager.set_agent_speaking(ucid, False, "emergency_stop")
            
            # Set interruption flag to stop any ongoing streaming
            call_state = interruption_manager.get_call_state(ucid)
            if call_state:
                call_state.is_interrupted = True
            
            log.info(f"✅ Emergency stop completed for {ucid}")
            
        except Exception as e:
            log.error(f"Error in emergency stop for {ucid}: {e}")
    
    @staticmethod
    def calculate_speech_duration(text: str, words_per_minute: float = 150.0) -> float:
        """
        Calculate estimated speech duration
        """
        if not text:
            return 0.0
        
        word_count = len(text.split())
        duration = (word_count / words_per_minute) * 60.0
        
        # Add minimum duration and buffer
        return max(2.0, duration + 1.0)