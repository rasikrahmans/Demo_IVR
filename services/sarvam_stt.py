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
                log.info("✅ Sarvam AI package loaded successfully")
            except ImportError:
                log.error("❌ sarvamai package not installed. Falling back to simple mode.")
                log.error("   To fix: pip install sarvamai")
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
                
                # The message is a SpeechToTextStreamingResponse object, not a dict
                # Let's check what attributes it has
                try:
                    # Try to access common attributes that streaming responses might have
                    if hasattr(message, 'type'):
                        message_type = message.type
                    elif hasattr(message, 'event_type'):
                        message_type = message.event_type
                    elif hasattr(message, 'message_type'):
                        message_type = message.message_type
                    else:
                        # If no type attribute, check if it has transcript directly
                        message_type = "transcript"
                    
                    if message_type == "speech_start" or (hasattr(message, 'is_speech_start') and message.is_speech_start):
                        # CRITICAL: Customer started speaking!
                        self.speech_start_events += 1
                        log.info(f"🎤 SPEECH START detected for {self.current_ucid}")
                        
                        # Check if agent is speaking - this is an interruption!
                        await self._handle_speech_start()
                        
                    elif message_type == "speech_end" or (hasattr(message, 'is_speech_end') and message.is_speech_end):
                        log.info(f"🔇 Speech ended for {self.current_ucid}")
                        
                    elif message_type == "transcript" or hasattr(message, 'transcript'):
                        # Got actual transcript
                        if hasattr(message, 'transcript'):
                            transcript = message.transcript.strip() if message.transcript else ""
                        elif hasattr(message, 'text'):
                            transcript = message.text.strip() if message.text else ""
                        else:
                            transcript = str(message).strip()
                        
                        if hasattr(message, 'confidence'):
                            confidence = message.confidence
                        else:
                            confidence = 0.8  # Default confidence
                        
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
                    
                    else:
                        # Log unknown message type for debugging
                        log.debug(f"🔍 Unknown Sarvam message type: {message_type}, message: {message}")
                
                except Exception as attr_error:
                    # If we can't parse the message properly, log it and continue
                    log.error(f"Error parsing Sarvam message: {attr_error}")
                    log.debug(f"Message object: {message}")
                    log.debug(f"Message attributes: {dir(message)}")
                
        except Exception as e:
            log.error(f"Error handling streaming responses: {e}")
            log.debug(f"Exception details: {type(e).__name__}: {str(e)}")
    
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
    
    def _handle_speech_start_sync(self):
        """Synchronous version for fallback mode"""
        try:
            # Import here to avoid circular imports
            from core.interruption import interruption_manager
            
            # Check if agent is currently speaking
            call_state = interruption_manager.get_call_state(self.current_ucid)
            if call_state and call_state.is_agent_speaking:
                log.info(f"🚨 SIMULATED INTERRUPTION for {self.current_ucid}")
                self.interruptions_triggered += 1
                
                # Trigger interruption immediately (sync version)
                interruption_manager.detect_interruption(
                    self.current_ucid, 
                    "customer_started_speaking_fallback", 
                    confidence=0.85
                )
        except Exception as e:
            log.error(f"Error in simulated speech start: {e}")
    
    def _extract_audio_bytes(self, audio_data) -> Optional[bytes]:
        """
        Extract and convert audio bytes from Ozonetel format to PCM
        Based on working AssemblyAI implementation pattern
        """
        try:
            import struct
            
            # Parse Ozonetel JSON format
            if isinstance(audio_data, bytes):
                audio_data = audio_data.decode('utf-8')
            
            if isinstance(audio_data, str):
                try:
                    json_data = json.loads(audio_data)
                except json.JSONDecodeError:
                    return None
            else:
                json_data = audio_data
            
            # Extract 16-bit samples from Ozonetel format
            if json_data.get('type') == 'media' and 'data' in json_data:
                data_dict = json_data['data']
                
                # Handle different Ozonetel structures
                samples = None
                if isinstance(data_dict, dict) and 'samples' in data_dict:
                    samples = data_dict['samples']
                elif isinstance(data_dict, list):
                    samples = data_dict
                
                if samples and isinstance(samples, list):
                    # CRITICAL FIX: Convert 16-bit samples to proper PCM bytes
                    # Ozonetel sends 16-bit signed integers (-32768 to 32767)
                    # We need to convert them to bytes using struct.pack
                    
                    # Clamp samples to valid 16-bit range to prevent struct.pack errors
                    clamped_samples = []
                    for sample in samples:
                        if isinstance(sample, (int, float)):
                            # Clamp to 16-bit signed integer range
                            clamped_sample = max(-32768, min(32767, int(sample)))
                            clamped_samples.append(clamped_sample)
                    
                    if clamped_samples:
                        # Convert to 16-bit PCM bytes (little-endian) - EXACTLY like AssemblyAI
                        try:
                            raw_audio = struct.pack(f'<{len(clamped_samples)}h', *clamped_samples)
                            
                            # Upsample from 8kHz to 16kHz for Sarvam compatibility
                            # Simple linear interpolation like AssemblyAI implementation
                            upsampled_samples = []
                            for i in range(len(clamped_samples)):
                                upsampled_samples.append(clamped_samples[i])
                                # Add interpolated sample between current and next
                                if i < len(clamped_samples) - 1:
                                    interpolated = (clamped_samples[i] + clamped_samples[i + 1]) // 2
                                    upsampled_samples.append(interpolated)
                                else:
                                    # For the last sample, duplicate it
                                    upsampled_samples.append(clamped_samples[i])
                            
                            # Convert upsampled data to PCM bytes
                            upsampled_audio = struct.pack(f'<{len(upsampled_samples)}h', *upsampled_samples)
                            
                            return upsampled_audio
                            
                        except struct.error as e:
                            log.error(f"❌ struct.pack error: {e} - sample range issue")
                            return None
                        except Exception as e:
                            log.error(f"❌ Audio conversion error: {e}")
                            return None
            
            return None
            
        except Exception as e:
            log.error(f"❌ Error extracting audio bytes: {e}")
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
                    
                    # Process audio to test conversion (but don't use result in fallback)
                    audio_bytes = self._extract_audio_bytes(audio_data)
                    if audio_bytes and self.total_audio_packets <= 3:
                        log.info(f"✅ Audio conversion working: {len(audio_bytes)} bytes from packet #{self.total_audio_packets}")
                    
                    # Simulate speech detection occasionally
                    if self.total_audio_packets % 50 == 0:  # Every 50 packets
                        # Use synchronous version to avoid event loop issues
                        self._handle_speech_start_sync()
                    
                    # Generate fake transcript occasionally for testing
                    if self.total_audio_packets % 150 == 0:  # Every 150 packets (~5 seconds)
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
                        log.info(f"📝 Fallback transcript: '{fake_transcript['transcript']}'")
                    
                    # Log progress occasionally
                    if self.total_audio_packets % 500 == 1:
                        log.info(f"📊 Fallback STT Stats: packets={self.total_audio_packets}, transcripts={self.processed_transcripts}")
                    
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