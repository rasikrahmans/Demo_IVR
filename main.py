"""
Demo Bot IVR - Main FastAPI Application
Clean implementation with Sarvam STT/TTS and interruption handling
"""

import logging
import uvicorn
from fastapi import FastAPI, Request, WebSocket, Query
from fastapi.responses import Response
from contextlib import asynccontextmanager

from config import Config
from api.webhook import WebhookHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(levelname)s:%(name)s:%(message)s'
)

log = logging.getLogger(__name__)

# Global webhook handler
webhook_handler = WebhookHandler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    try:
        # Validate configuration
        Config.validate()
        log.info(f"🚀 Starting {Config.APP_NAME}")
        log.info(f"📦 Ready to handle parcel tracking inquiries")
        yield
    except Exception as e:
        log.error(f"❌ Configuration error: {e}")
        raise
    finally:
        log.info("🛑 Shutting down Demo Bot IVR")

# Create FastAPI app
app = FastAPI(
    title=Config.APP_NAME,
    description="Clean demo bot IVR with Sarvam STT/TTS and interruption handling",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": Config.APP_NAME,
        "version": "1.0.0"
    }

@app.get("/hook")
async def inbound_hook(
    request: Request,
    event: str = Query(None),
    sid: str = Query(None),
    ucid: str = Query(None),
    cid: str = Query(None),
    cid_e164: str = Query(None),
    called_number: str = Query(None)
):
    """
    Ozonetel inbound call webhook
    """
    return await webhook_handler.handle_inbound_call(
        request=request,
        event=event,
        sid=sid,
        ucid=ucid,
        cid=cid,
        cid_e164=cid_e164,
        called_number=called_number
    )

@app.get("/test-ws")
async def test_websocket():
    """Test WebSocket endpoint accessibility"""
    return {
        "status": "WebSocket endpoint available",
        "websocket_url": f"ws://{Config.WEBHOOK_ENDPOINT}/ws",
        "test_url": f"ws://{Config.WEBHOOK_ENDPOINT}/ws?ucid=test&cid=test",
        "message": "Use a WebSocket client to test connection to the URL above"
    }

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ucid: str = Query(None),
    cid: str = Query(None)
):
    """
    WebSocket endpoint for real-time voice processing
    """
    await webhook_handler.handle_websocket_connection(websocket, ucid, cid)

@app.get("/stats")
async def get_stats():
    """Get call statistics"""
    return webhook_handler.get_stats()

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": Config.APP_NAME,
        "sarvam_configured": bool(Config.SARVAM_API_KEY),
        "ozonetel_configured": bool(Config.OZONETEL_API_KEY),
        "webhook_endpoint": Config.WEBHOOK_ENDPOINT,
        "active_calls": len([c for c in webhook_handler.active_calls.values() if c['status'] == 'active'])
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=Config.SERVER_HOST,
        port=Config.SERVER_PORT,
        log_level=Config.LOG_LEVEL.lower(),
        reload=Config.DEBUG
    )