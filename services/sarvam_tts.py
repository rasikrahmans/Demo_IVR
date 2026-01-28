"""
Sarvam TTS Service with streaming support
Clean implementation for real-time audio generation
"""

import asyncio
import websockets
import json
import logging
import base64
from typing import AsyncGenerator, Optional

from config import Config
from core.interruption import interruption_manager
from core.audio_streaming import AudioStreamer

log = logging.getLogger(__name__)

class SarvamTTSService:
    """
    Clean Sarvam TTS service with streaming support
    """
    
    def __init__(self):
        self.api_key = Config.SARVAM_API_KEY
        self.base_url = Config.SARVAM_TTS_URL
        self.enabled = bool(self.api_key)
        
        # TTS Configuration
        self.model = "bulbul:v2"
        self.speaker = "meera"  # English Indian voice
        self.target_language = "en-IN"
        
        # Connection state
        self.websocket = None
        self.is_connected = False
        
        if not self.enabled:
            log.warning("⚠️ Sarvam API key not configured - TTS will be simulated")
        else:
            log.info(f"✅ Sarvam TTS Service initialized - Speaker: {self.speaker}")
    
    async def connect(self) -> bool:
        """Connect to Sarvam TTS WebSocket"""
        try:
            if not self.api_key:
                log.error("❌ No Sarvam API key found")
                return False
            
            headers = {
                "Api-Subscription-Key": self.api_key
            }
            
            log.info(f"🔗 Connecting to Sarvam TTS...")
            
            self.websocket = await websockets.connect(
                self.base_url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            log.info("✅ Connected to Sarvam TTS service")
            
            # Configure the TTS session
            await self._configure_session()
            
            return True
            
        except Exception as e:
            log.error(f"❌ Failed to connect to Sarvam TTS: {e}")
            self.is_connected = False
            return False
    
    async def _configure_session(self):
        """Configure the TTS session"""
        try:
            config_message = {
                "model": self.model,
                "target_language_code": self.target_language,
                "speaker": self.speaker,
                "send_completion_event": True
            }
            
            await self.websocket.send(json.dumps(config_message))
            log.info(f"🎤 Configured TTS session: {self.speaker} voice, {self.target_language}")
            
        except Exception as e:
            log.error(f"Error configuring TTS session: {e}")
    
    async def disconnect(self):
        """Disconnect from Sarvam TTS"""
        try:
            if self.websocket and self.is_connected:
                await self.websocket.close()
            self.is_connected = False
            self.websocket = None
        except Exception as e:
            log.error(f"Error disconnecting from Sarvam TTS: {e}")
    
    async def generate_speech_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Generate speech audio from text as a stream of audio chunks
        """
        if not self.enabled:
            log.info(f"Simulating streaming TTS for: '{text[:50]}...'")
            # Return silence for simulation
            yield self._generate_silence_chunk()
            return
        
        try:
            # Connect if not already connected
            if not self.is_connected:
                if not await self.connect():
                    log.error("Failed to connect to Sarvam TTS")
                    return
            
            log.info(f"🎤 Generating streaming TTS: '{text[:50]}...'")
            
            # Send text for conversion
            convert_message = {"text": text}
            await self.websocket.send(json.dumps(convert_message))
            
            # Send flush signal to start generation
            flush_message = {"flush": True}
            await self.websocket.send(json.dumps(flush_message))
            
            # Receive and yield audio chunks
            chunk_count = 0
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    
                    # Handle audio chunks
                    if "audio" in data:
                        audio_base64 = data["audio"]
                        audio_chunk = base64.b64decode(audio_base64)
                        chunk_count += 1
                        
                        log.debug(f"📊 Received audio chunk {chunk_count}: {len(audio_chunk)} bytes")
                        yield audio_chunk
                    
                    # Handle completion event
                    elif "event_type" in data:
                        event_type = data["event_type"]
                        if event_type == "final":
                            log.info(f"✅ Streaming TTS completed: {chunk_count} chunks")
                            break
                    
                    # Handle errors
                    elif "error" in data:
                        error_msg = data["error"]
                        log.error(f"Sarvam TTS error: {error_msg}")
                        break
                        
                except json.JSONDecodeError:
                    # Might be raw audio data
                    continue
                except Exception as e:
                    log.error(f"Error processing TTS message: {e}")
                    break
                
        except Exception as e:
            log.error(f"Error in streaming TTS: {e}")
    
    async def generate_speech(self, text: str, language_code: str = "en-IN") -> Optional[bytes]:
        """
        Generate complete speech audio from text (for compatibility)
        """
        try:
            audio_chunks = []
            
            async for chunk in self.generate_speech_stream(text):
                audio_chunks.append(chunk)
            
            if audio_chunks:
                complete_audio = b''.join(audio_chunks)
                log.info(f"✅ Complete TTS generated: {len(complete_audio)} bytes")
                return complete_audio
            else:
                return None
                
        except Exception as e:
            log.error(f"Error generating complete speech: {e}")
            return None
    
    async def speak_with_interruption(self, websocket, text: str, ucid: str) -> bool:
        """
        Generate and stream TTS with interruption support
        
        Args:
            websocket: WebSocket connection to Ozonetel
            text: Text to convert to speech
            ucid: Unique call ID
            
        Returns:
            True if completed, False if interrupted
        """
        try:
            word_count = len(text.split())
            interruption_manager.set_agent_speaking(ucid, True, f"speaking_{word_count}_words")
            
            log.info(f"🤖 Agent speaking: '{text[:60]}...'")
            
            if self.enabled:
                # Use streaming TTS for real-time generation
                success = await self._stream_tts_with_interruption(websocket, text, ucid)
            else:
                # Fallback to simulated audio
                audio_bytes = self._generate_silence_chunk()
                success = await AudioStreamer.stream_audio_with_interruption(websocket, audio_bytes, ucid)
            
            if success:
                interruption_manager.set_agent_speaking(ucid, False, "speech_completed")
                log.info(f"✅ Speech completed successfully for {ucid}")
                return True
            else:
                interruption_manager.set_agent_speaking(ucid, False, "speech_interrupted")
                log.info(f"🛑 Speech was interrupted for {ucid}")
                return False
                
        except Exception as e:
            log.error(f"❌ Error in speak_with_interruption: {e}")
            interruption_manager.set_agent_speaking(ucid, False, "speech_error")
            return False
    
    async def _stream_tts_with_interruption(self, websocket, text: str, ucid: str) -> bool:
        """Stream TTS audio chunks with interruption checking"""
        try:
            import time
            
            chunk_count = 0
            
            async for audio_chunk in self.generate_speech_stream(text):
                # CRITICAL: Check for interruption before sending each chunk
                if interruption_manager.is_interrupted(ucid):
                    log.error(f"🛑 INTERRUPTION - Stopping TTS at chunk {chunk_count+1}")
                    return False
                
                # Send audio chunk to Ozonetel immediately
                try:
                    audio_message = {
                        "type": "audio",
                        "ucid": ucid,
                        "data": list(audio_chunk),
                        "timestamp": time.time()
                    }
                    
                    await websocket.send(json.dumps(audio_message))
                    chunk_count += 1
                    
                    # CRITICAL: Check for interruption after sending each chunk
                    if interruption_manager.is_interrupted(ucid):
                        log.error(f"🛑 INTERRUPTION AFTER CHUNK {chunk_count} - Stopping immediately")
                        return False
                    
                    # Small delay for interruption responsiveness
                    await asyncio.sleep(0.001)  # 1ms delay - very responsive
                    
                except Exception as e:
                    log.error(f"Error sending TTS chunk {chunk_count+1}: {e}")
                    return False
            
            log.info(f"✅ Streaming TTS completed: {chunk_count} chunks for {ucid}")
            return True
            
        except Exception as e:
            log.error(f"Error in streaming TTS: {e}")
            return False
    
    def _generate_silence_chunk(self) -> bytes:
        """Generate a small silence chunk for simulation"""
        try:
            import struct
            
            # Generate 100ms of silence at 16kHz
            sample_rate = 16000
            duration_ms = 100
            num_samples = (sample_rate * duration_ms) // 1000
            
            # Create silence (zeros)
            silence_data = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
            return silence_data
            
        except Exception as e:
            log.error(f"Error generating silence: {e}")
            return b''