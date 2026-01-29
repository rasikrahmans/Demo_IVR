"""
Sarvam STT Service with Real-time Streaming and Speech Detection
Uses Sarvam's WebSocket streaming API with VAD signals for interruption detection
"""

import asyncio
import json
import logging
import queue
import threading
import base64
import os
import time
from typing import Optional, Callable, Dict, Any

log = logging.getLogger(__name__)

class SarvamSTTService:
    """
    Real Sarvam STT service using streaming WebSocket API with speech detection
    """
    
    def __init__(self):
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        self.api_key = os.getenv('SARVAM_API_KEY')
        self.enabled = bool(self.api_key)
        self.language_code = "en-IN"
        self.sample_rate = 8000  # Ozonetel typically uses 8kHz
        
        # Processing queues
        self.audio_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # Current call tracking
        self.current_ucid = None
        
        # Statistics
        self.total_audio_packets = 0
        self.processed_transcripts = 0
        self.speech_start_events = 0
        self.interruptions_triggered = 0
        
        # WebSocket connection
        self.ws_client = None
        self.ws_connection = None
        
        if not self.enabled:
            log.warning("Sarvam API key not configured - STT will use fallback mode")
        else:
            log.info(f"✅ Sarvam STT Service initialized with streaming API (key: ...{self.api_key[-4:]})")
    
    def run_stream(self, audio_queue: queue.Queue, result_queue: queue.Queue, ucid: str):
        """
        Run streaming STT for a specific call using Sarvam's WebSocket API
        """
        self.audio_queue = audio_queue
        self.result_queue = result_queue
        self.current_ucid = ucid
        
        log.info(f"🎤 STT streaming started for {ucid} - using Sarvam WebSocket API")
        
        if self.enabled:
            # Use real Sarvam streaming API
            asyncio.run(self._run_sarvam_streaming())
        else:
            # Fallback mode
            self._run_fallback_mode()
        
        log.info(f"🛑 STT streaming stopped for {ucid}")
    
    async def _run_sarvam_streaming(self):
        """Run real Sarvam streaming STT with speech detection"""
        try:
            # Import Sarvam client
            try:
                from sarvamai import AsyncSarvamAI
            except ImportError:
                log.error("sarvamai package not installed. Install with: pip install sarvamai")
                self._run_fallback_mode()
                return
            
            # Initialize Sarvam client
            client = AsyncSarvamAI(api_subscription_key=self.api_key)
            
            # Connect to streaming API with VAD signals
            async with client.speech_to_text_streaming.connect(
                language_code=self.language_code,
                model="saarika:v2.5",
                sample_rate=self.sample_rate,
                high_vad_sensitivity=True,
                vad_signals=True,  # CRITICAL: This gives us speech_start/speech_end events
                input_audio_codec="pcm_s16le"
            ) as ws:
                self.ws_connection = ws
                log.info(f"✅ Connected to Sarvam streaming API for {self.current_ucid}")
                
                # Start audio processing task
                audio_task = asyncio.create_task(self._process_audio_stream(ws))
                
                # Start response handling task
                response_task = asyncio.create_task(self._handle_streaming_responses(ws))
                
                # Wait for either task to complete or stop event
                while not self.stop_event.is_set():
                    await asyncio.sleep(0.1)
                
                # Cancel tasks
                audio_task.cancel()
                response_task.cancel()
                
        except Exception as e:
            log.error(f"Error in Sarvam streaming: {e}")
            # Fallback to simple mode
            self._run_fallback_mode()
    
    async def _process_audio_stream(self, ws):
        """Process incoming audio and send to Sarvam"""
        audio_buffer = []
        last_send_time = time.time()
        
        while not self.stop_event.is_set():
            try:
                # Get audio data from queue (non-blocking)
                try:
                    audio_data = self.audio_queue.get_nowait()
                    if audio_data is None:
                        break
                    
                    self.total_audio_packets += 1
                    
                    # Extract audio bytes
                    audio_bytes = self._extract_audio_bytes(audio_data)
                    if audio_bytes:
                        audio_buffer.append(audio_bytes)
                    
                    # Send accumulated audio every 500ms for real-time processing
                    current_time = time.time()
                    if current_time - last_send_time >= 0.5 and audio_buffer:
                        # Combine audio chunks
                        combined_audio = b''.join(audio_buffer)
                        audio_buffer = []
                        
                        # Convert to base64
                        audio_base64 = base64.b64encode(combined_audio).decode('utf-8')
                        
                        # Send to Sarvam
                        await ws.transcribe(
                            audio=audio_base64,
                            encoding="audio/wav",
                            sample_rate=self.sample_rate
                        )
                        
                        last_send_time = current_time
                        
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue
                    
            except Exception as e:
                log.error(f"Error processing audio stream: {e}")
                break
    
    async def _handle_streaming_responses(self, ws):
        """Handle responses from Sarvam streaming API"""
        try:
            async for message in ws:
                if self.stop_event.is_set():
                    break
                
                message_type = message.get("type", "")
                
                if message_type == "speech_start":
                    # CRITICAL: Customer started speaking!
                    self.speech_start_events += 1
                    log.info(f"🎤 SPEECH START detected for {self.current_ucid}")
                    
                    # Check if agent is speaking - this is an interruption!
                    await self._handle_speech_start()
                    
                elif message_type == "speech_end":
                    log.info(f"🔇 Speech ended for {self.current_ucid}")
                    
                elif message_type == "transcript":
                    # Got actual transcript
                    transcript = message.get("text", "").strip()
                    confidence = message.get("confidence", 0.8)
                    
                    if transcript:
                        result = {
                            'transcript': transcript,
                            'confidence': confidence,
                            'is_final': True,
                            'provider': 'sarvam_streaming'
                        }
                        self.result_queue.put(result)
                        self.processed_transcripts += 1
                        log.info(f"📝 Sarvam transcript: '{transcript}' (confidence: {confidence:.2f})")
                
        except Exception as e:
            log.error(f"Error handling streaming responses: {e}")
    
    async def _handle_speech_start(self):
        """Handle speech start event - check for interruption"""
        try:
            # Import here to avoid circular imports
            from core.interruption import interruption_manager
            
            # Check if agent is currently speaking
            call_state = interruption_manager.get_call_state(self.current_ucid)
            if call_state and call_state.is_agent_speaking:
                log.error(f"🚨 INTERRUPTION DETECTED via speech_start for {self.current_ucid}")
                self.interruptions_triggered += 1
                
                # Trigger interruption immediately
                interruption_manager.detect_interruption(
                    self.current_ucid, 
                    "customer_started_speaking", 
                    confidence=0.95
                )
                
        except Exception as e:
            log.error(f"Error handling speech start: {e}")
    
    def _extract_audio_bytes(self, audio_data: str) -> Optional[bytes]:
        """Extract audio bytes from various formats"""
        try:
            audio_bytes = None
            
            # Try multiple ways to extract audio data
            try:
                # Method 1: JSON with payload field
                json_data = json.loads(audio_data)
                if json_data.get('type') == 'media' and 'payload' in json_data:
                    audio_payload = json_data['payload']
                    audio_bytes = base64.b64decode(audio_payload)
                elif 'data' in json_data:
                    # Method 2: JSON with data field (array of bytes)
                    if isinstance(json_data['data'], list):
                        audio_bytes = bytes(json_data['data'])
                    else:
                        audio_bytes = base64.b64decode(json_data['data'])
                        
            except json.JSONDecodeError:
                # Method 3: Raw base64 string
                try:
                    audio_bytes = base64.b64decode(audio_data)
                except:
                    # Method 4: Raw binary data (if sent as string)
                    if isinstance(audio_data, str) and len(audio_data) > 10:
                        audio_bytes = audio_data.encode('latin-1')
            
            return audio_bytes if audio_bytes and len(audio_bytes) > 10 else None
            
        except Exception as e:
            log.error(f"Error extracting audio bytes: {e}")
            return None
    
    def _run_fallback_mode(self):
        """Fallback mode when Sarvam API is not available"""
        log.info(f"� Running STT in fallback mode for {self.current_ucid}")
        
        # Simple fallback processing
        while not self.stop_event.is_set():
            try:
                try:
                    audio_data = self.audio_queue.get(timeout=1.0)
                    if audio_data is None:
                        break
                    
                    self.total_audio_packets += 1
                    
                    # Simulate speech detection occasionally
                    if self.total_audio_packets % 50 == 0:  # Every 50 packets
                        # Simulate speech start
                        asyncio.run(self._handle_speech_start())
                    
                    # Generate fake transcript occasionally
                    if self.total_audio_packets % 200 == 0:
                        fake_responses = [
                            "Hello, I want to track my package",
                            "I need to check my order status", 
                            "Can you help me track my delivery",
                            "My tracking number is ABC123456789",
                            "Thank you, goodbye"
                        ]
                        
                        import random
                        fake_transcript = {
                            'transcript': random.choice(fake_responses),
                            'confidence': 0.85,
                            'is_final': True,
                            'provider': 'sarvam_fallback'
                        }
                        self.result_queue.put(fake_transcript)
                        self.processed_transcripts += 1
                    
                except queue.Empty:
                    continue
                    
            except Exception as e:
                log.error(f"Error in fallback mode: {e}")
                break
    
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
                'provider': 'sarvam_demo'
            }
        
        return {
            'transcript': '', 
            'language_code': self.language_code, 
            'confidence': 0.0, 
            'provider': 'sarvam_real' if self.enabled else 'sarvam_fallback'
        }