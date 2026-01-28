"""
Sarvam STT Service with Voice Activity Detection (VAD)
Clean implementation for interruption detection
"""

import asyncio
import websockets
import json
import logging
import queue
import threading
import struct
from typing import Optional, Callable, Dict, Any

from config import Config
from core.interruption import interruption_manager

log = logging.getLogger(__name__)

class SarvamSTTService:
    """
    Clean Sarvam STT service with VAD for interruption detection
    """
    
    def __init__(self):
        self.api_key = Config.SARVAM_API_KEY
        self.base_url = Config.SARVAM_STT_URL
        self.enabled = bool(self.api_key)
        
        # STT Configuration
        self.language_code = "en-IN"
        self.model = "saaras:v3"
        self.sample_rate = 16000
        
        # Connection state
        self.websocket = None
        self.is_connected = False
        
        # Processing queues
        self.audio_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # Current call tracking
        self.current_ucid = None
        
        # Statistics
        self.total_audio_packets = 0
        self.processed_transcripts = 0
        
        if not self.enabled:
            log.warning("⚠️ Sarvam API key not configured - STT will be simulated")
        else:
            log.info(f"✅ Sarvam STT Service initialized - Language: {self.language_code}")
    
    async def connect(self) -> bool:
        """Connect to Sarvam STT WebSocket"""
        try:
            if not self.api_key:
                log.error("❌ No Sarvam API key found")
                return False
            
            # Build WebSocket URL with parameters
            params = {
                "language-code": self.language_code,
                "model": self.model,
                "sample_rate": str(self.sample_rate),
                "vad_signals": "true",  # Enable VAD for interruption detection
                "high_vad_sensitivity": "true",  # High sensitivity for quick detection
                "input_audio_codec": "pcm_s16le"
            }
            
            param_string = "&".join([f"{k}={v}" for k, v in params.items()])
            ws_url = f"{self.base_url}?{param_string}"
            
            headers = {
                "Api-Subscription-Key": self.api_key
            }
            
            log.info(f"🔗 Connecting to Sarvam STT...")
            
            self.websocket = await websockets.connect(
                ws_url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            log.info("✅ Connected to Sarvam STT service")
            
            # Start message handler
            asyncio.create_task(self._handle_messages())
            return True
            
        except Exception as e:
            log.error(f"❌ Failed to connect to Sarvam STT: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Sarvam STT"""
        try:
            if self.websocket and self.is_connected:
                await self.websocket.close()
            self.is_connected = False
            self.websocket = None
        except Exception as e:
            log.error(f"Error disconnecting from Sarvam STT: {e}")
    
    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                await self._process_message(message)
        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
            log.info("Sarvam STT connection closed")
        except Exception as e:
            log.error(f"Sarvam STT error: {e}")
            self.is_connected = False
    
    async def _process_message(self, message: str):
        """Process incoming message from Sarvam STT"""
        try:
            data = json.loads(message)
            
            # Handle VAD (Voice Activity Detection) signals
            if "vad_signal" in data:
                await self._handle_vad_signal(data)
            
            # Handle transcription results
            if "transcript" in data:
                await self._handle_transcript(data)
            
            # Handle errors
            if "error" in data:
                error_msg = data.get("error", "Unknown error")
                log.error(f"Sarvam STT error: {error_msg}")
                
        except json.JSONDecodeError as e:
            log.error(f"Error decoding Sarvam STT message: {e}")
        except Exception as e:
            log.error(f"Error processing Sarvam STT message: {e}")
    
    async def _handle_vad_signal(self, data: dict):
        """Handle Voice Activity Detection signals"""
        try:
            vad_type = data.get("vad_signal")
            
            if not self.current_ucid:
                return
            
            if vad_type == "speech_start":
                log.info(f"🎤 VAD: Customer started speaking - {self.current_ucid}")
                
                # Check if agent is currently speaking - this is an interruption!
                call_state = interruption_manager.get_call_state(self.current_ucid)
                if call_state and call_state.is_agent_speaking:
                    log.error(f"🛑 VAD INTERRUPTION: Customer speaking while agent is speaking!")
                    
                    # Trigger interruption detection
                    interruption_manager.detect_interruption(
                        self.current_ucid, 
                        "VAD_DETECTED_SPEECH", 
                        1.0
                    )
            
            elif vad_type == "speech_end":
                log.info(f"🎤 VAD: Customer stopped speaking - {self.current_ucid}")
            
            elif vad_type == "voice_activity":
                # Immediate voice activity detected
                call_state = interruption_manager.get_call_state(self.current_ucid)
                if call_state and call_state.is_agent_speaking:
                    log.error(f"🚨 VAD: Immediate voice activity during agent speech - INTERRUPTION!")
                    interruption_manager.detect_interruption(
                        self.current_ucid, 
                        "VAD_VOICE_ACTIVITY", 
                        1.0
                    )
                
        except Exception as e:
            log.error(f"Error in VAD signal handling: {e}")
    
    async def _handle_transcript(self, data: dict):
        """Handle transcription results"""
        try:
            transcript = data.get("transcript", "").strip()
            is_final = data.get("is_final", False)
            confidence = data.get("confidence", 0.0)
            
            if transcript and is_final and self.current_ucid:
                self.processed_transcripts += 1
                
                # Create result in expected format
                result = {
                    'transcript': transcript,
                    'confidence': confidence,
                    'is_final': True,
                    'provider': 'sarvam_streaming'
                }
                
                # Add to result queue
                self.result_queue.put(result)
                
                # CRITICAL: Check for interruption based on transcript
                interruption_manager.detect_interruption(self.current_ucid, transcript, confidence)
                
                log.info(f"📝 Sarvam STT: '{transcript}' (confidence: {confidence:.2f})")
                
        except Exception as e:
            log.error(f"Error handling transcript: {e}")
    
    async def send_audio(self, ozonetel_audio_data: str):
        """Send audio data to Sarvam STT"""
        try:
            if not self.websocket or not self.is_connected:
                return False
            
            # Parse Ozonetel JSON format and extract PCM audio
            data = json.loads(ozonetel_audio_data)
            
            if data.get('type') == 'media' and 'data' in data:
                samples = data['data'].get('samples', [])
                if samples:
                    # Upsample from 8kHz to 16kHz if needed
                    if len(samples) == 80:  # 8kHz, 10ms
                        upsampled_samples = []
                        for sample in samples:
                            upsampled_samples.extend([sample, sample])  # Simple duplication
                        samples = upsampled_samples
                    
                    # Convert to 16-bit PCM bytes
                    pcm_audio = struct.pack(f'<{len(samples)}h', *samples)
                    
                    # Send PCM audio to Sarvam
                    await self.websocket.send(pcm_audio)
                    self.total_audio_packets += 1
                    return True
            
            return False
                
        except Exception as e:
            log.error(f"Error sending audio to Sarvam STT: {e}")
            return False
    
    def run_stream(self, audio_queue: queue.Queue, result_queue: queue.Queue, ucid: str):
        """
        Run streaming STT for a specific call
        """
        self.audio_queue = audio_queue
        self.result_queue = result_queue
        self.current_ucid = ucid
        
        # Run async event loop
        asyncio.run(self._run_stream_async())
    
    async def _run_stream_async(self):
        """Async implementation of streaming STT"""
        try:
            # Connect to Sarvam STT
            if not await self.connect():
                log.error("Failed to connect to Sarvam STT")
                return
            
            # Process audio queue
            while self.is_connected and not self.stop_event.is_set():
                try:
                    # Get audio data from queue (non-blocking)
                    try:
                        ozonetel_audio_data = self.audio_queue.get_nowait()
                        if ozonetel_audio_data is None:
                            break
                        
                        # Send audio to Sarvam STT
                        await self.send_audio(ozonetel_audio_data)
                        
                    except queue.Empty:
                        # No audio data available, wait a bit
                        await asyncio.sleep(0.01)
                        continue
                    
                except Exception as e:
                    log.error(f"Error processing audio queue: {e}")
                    break
            
        except Exception as e:
            log.error(f"Error in Sarvam STT stream: {e}")
        finally:
            await self.disconnect()
            log.info("Sarvam streaming STT stopped")
    
    def stop(self):
        """Stop the STT service"""
        self.stop_event.set()
    
    def get_final_transcript(self, result) -> Dict[str, Any]:
        """Extract final transcript from result"""
        if isinstance(result, dict):
            return {
                'transcript': result.get('transcript', ''),
                'language_code': self.language_code,
                'confidence': result.get('confidence', 0.0),
                'provider': 'sarvam_streaming'
            }
        
        return {
            'transcript': '', 
            'language_code': self.language_code, 
            'confidence': 0.0, 
            'provider': 'sarvam_streaming'
        }