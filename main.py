"""
Parcel Tracking Voice Agent
Main entry point for the voice-based parcel tracking system
"""

import uvicorn
import logging
from api.webhook import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

log = logging.getLogger(__name__)

if __name__ == "__main__":
    log.info("🚀 Starting Parcel Tracking Voice Agent")
    log.info("📦 Ready to handle parcel tracking inquiries")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=True,
        ws_ping_interval=20,
        ws_ping_timeout=20
    )