"""
Sarvam TTS Service for Parcel Tracking Agent
Provides text-to-speech conversion using Sarvam API
"""

import requests
import logging
import os
import tempfile
from typing import Optional

log = logging.getLogger(__name__)

class SarvamTTSService:
    """Sarvam Text-to-Speech service"""
    
    def __init__(self):
        self.api_key = os.getenv('SARVAM_API_KEY')
        self.base_url = "https://api.sarvam.ai/text-to-speech"
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            log.warning("Sarvam API key not configured - TTS will be simulated")
        else:
            log.info(f"Sarvam TTS Service initialized")
    
    def generate_speech(self, text: str, language_code: str = "en-IN") -> Optional[bytes]:
        """Generate speech audio from text
        
        Args:
            text: Text to convert to speech
            language_code: Language code (en-IN, hi-IN)
            
        Returns:
            Audio bytes in WAV format or None if failed
        """
        if not self.enabled:
            # Return empty audio bytes for simulation
            return self._generate_silence(len(text.split()) * 0.5)
        
        try:
            # Map language codes to Sarvam voices
            voice_mapping = {
                "en-IN": "meera",  # English Indian voice
                "hi-IN": "arjun",  # Hindi voice
            }
            
            voice = voice_mapping.get(language_code, "meera")
            
            headers = {
                "Content-Type": "application/json",
                "API-Subscription-Key": self.api_key
            }
            
            payload = {
                "text": text,
                "language_code": language_code,
                "speaker": "abhilash" if language_code == "en-IN" else "manisha",
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.5,
                "speech_sample_rate": 8000,
                "enable_preprocessing": True,
                "model": "bulbul:v2"
            }
            
            log.debug(f"🎤 Generating TTS: '{text[:30]}...' (speaker: abhilash)")
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'audios' in result and len(result['audios']) > 0:
                    # Get base64 audio data
                    audio_base64 = result['audios'][0]
                    
                    # Decode base64 to bytes
                    import base64
                    audio_bytes = base64.b64decode(audio_base64)
                    
                    log.info(f"✅ TTS generated: {len(audio_bytes)} bytes")
                    return audio_bytes
                else:
                    log.error("No audio data in Sarvam response")
                    return None
            else:
                log.error(f"Sarvam TTS error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            log.error(f"Error generating speech: {e}")
            return None
    
    def _generate_silence(self, duration_seconds: float) -> bytes:
        """Generate silence audio for simulation
        
        Args:
            duration_seconds: Duration of silence
            
        Returns:
            WAV audio bytes with silence
        """
        try:
            import struct
            import wave
            import io
            
            sample_rate = 16000
            num_samples = int(sample_rate * duration_seconds)
            
            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                
                # Write silence (zeros)
                silence_data = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
                wav_file.writeframes(silence_data)
            
            wav_buffer.seek(0)
            return wav_buffer.read()
            
        except Exception as e:
            log.error(f"Error generating silence: {e}")
            return b''
    
    def is_enabled(self) -> bool:
        """Check if TTS service is enabled"""
        return self.enabled