"""
Configuration management for Demo Bot IVR
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    
    # Sarvam API
    SARVAM_API_KEY = os.getenv('SARVAM_API_KEY')
    SARVAM_STT_URL = "wss://api.sarvam.ai/speech-to-text/ws"
    SARVAM_TTS_URL = "wss://api.sarvam.ai/text-to-speech/ws"
    
    # AWS & Bedrock
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    BEDROCK_MODEL_ID = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
    BEDROCK_TEMPERATURE = float(os.getenv('BEDROCK_TEMPERATURE', '0.7'))
    
    # Ozonetel
    OZONETEL_API_KEY = os.getenv('OZONETEL_API_KEY')
    OZONETEL_CALLER_ID = os.getenv('OZONETEL_CALLER_ID')
    OZONETEL_SIP_NUMBER = os.getenv('OZONETEL_SIP_NUMBER')
    
    # Server
    SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.getenv('SERVER_PORT', '8000'))
    WEBHOOK_ENDPOINT = os.getenv('WEBHOOK_ENDPOINT')
    
    # Application
    APP_NAME = os.getenv('APP_NAME', 'Demo Bot IVR')
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            'SARVAM_API_KEY',
            'OZONETEL_API_KEY',
            'WEBHOOK_ENDPOINT'
        ]
        
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        
        return True