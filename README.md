# Demo Bot IVR

A clean, simple IVR bot for parcel tracking with:
- Sarvam STT (Speech-to-Text) with VAD interruption detection
- Sarvam TTS (Text-to-Speech) with streaming
- Strands agent for conversation handling
- Ozonetel integration
- Real-time interruption handling

## Features

- ✅ Clean, minimal codebase
- ✅ Sarvam STT with Voice Activity Detection (VAD)
- ✅ Sarvam streaming TTS for better audio quality
- ✅ Immediate interruption detection and buffer clearing
- ✅ Strands agent for intelligent conversation
- ✅ Parcel tracking simulation
- ✅ Ozonetel phone integration

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the bot
python main.py
```

## Architecture

```
demo_bot_ivr/
├── main.py                 # FastAPI server entry point
├── config.py              # Configuration management
├── requirements.txt       # Dependencies
├── .env.example           # Environment template
├── services/
│   ├── sarvam_stt.py     # Sarvam STT with VAD
│   ├── sarvam_tts.py     # Sarvam streaming TTS
│   ├── conversation.py    # Strands conversation agent
│   └── ozonetel.py       # Ozonetel integration
├── core/
│   ├── interruption.py   # Interruption detection & buffer management
│   └── audio_streaming.py # Audio streaming with interruption support
└── api/
    └── webhook.py        # Ozonetel webhook handlers
```