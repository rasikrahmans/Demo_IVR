"""
Sarvam STT Service with Voice Activity Detection (VAD)
Simplified implementation for interruption detection
"""

import asyncio
import json
import logging
import queue
import threading
import struct
from typing import Optional, Callable, Dict, Any

log = logging.getLogger(__name__)

class SarvamSTTService:
    """
    Simplified Sarvam STT service for demo purposes
    """
    
    def __init__(self):
        self.enabled = False  # Simplified - no real STT for now
        self.language_code = "en-IN"
        self.sample_rate = 16000
        
        # Processing queues
        self.audio_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # Current call tracking
        self.current_ucid = None
        
        # Statistics
        self.total_audio_packets = 0
        self.processed_transcripts = 0
        
        log.info(f"✅ Sarvam STT Service initialized (simplified mode)")
    
    def run_stream(self, audio_queue: queue.Queue, result_queue: queue.Queue, ucid: str):
        """
        Run streaming STT for a specific call (simplified)
        """
        self.audio_queue = audio_queue
        self.result_queue = result_queue
        self.current_ucid = ucid
        
        log.info(f"🎤 STT processing started for {ucid} (simplified mode)")
        
        # Simple loop that processes audio but doesn't do real transcription
        while not self.stop_event.is_set():
            try:
                # Get audio data from queue
                try:
                    audio_data = self.audio_queue.get(timeout=1.0)
                    if audio_data is None:
                        break
                    
                    self.total_audio_packets += 1
                    
                    # For demo purposes, occasionally generate fake transcripts
                    if self.total_audio_packets % 200 == 0:  # Every 200 packets instead of 50
                        fake_transcript = {
                            'transcript': 'Hello, I want to track my package',
                            'confidence': 0.85,
                            'is_final': True,
                            'provider': 'sarvam_demo'
                        }
                        self.result_queue.put(fake_transcript)
                    
                except queue.Empty:
                    continue
                    
            except Exception as e:
                log.error(f"Error in STT processing: {e}")
                break
        
        log.info(f"🛑 STT processing stopped for {ucid}")
    
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
            'provider': 'sarvam_demo'
        }