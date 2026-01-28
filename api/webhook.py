"""Parcel Tracking Voice Agent API
Handles inbound calls for parcel tracking inquiries"""

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from datetime import datetime
import logging
import asyncio
import queue
import threading
import json
import os
from typing import Dict, Optional

# Import services
from services.sarvam_stt import SarvamSTTService
from services.sarvam_tts import SarvamTTSService
from services.conversation import ParcelTrackingAgent
from services.ozonetel import OzonetelService
from core.interruption import interruption_manager
from core.audio_streaming import AudioStreamer

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(
    title="Parcel Tracking Voice Agent",
    description="Voice-based parcel tracking system with interruption handling",
    version="1.0.0"
)

# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

# Store active call sessions
call_sessions: Dict[str, Dict] = {}

@app.get("/hook")
@app.post("/hook")
async def inbound_hook(
    request: Request,
    event: str = None,
    sid: str = None,
    ucid: str = None,
    cid: str = None,
    cid_e164: str = None,
    called_number: str = None
):
    """Ozonetel inbound call webhook
    Handles incoming calls and directs them to WebSocket"""
    try:
        call_id = sid or ucid or "unknown"
        caller_id = cid or cid_e164 or "unknown"
        
        log.info(f"📞 Inbound call - Event: {event}, UCID: {call_id}, Caller: {caller_id}")
        
        if event == "NewCall" or event is None:
            # Create call session
            call_sessions[call_id] = {
                'call_id': call_id,
                'caller_id': caller_id,
                'start_time': datetime.now().isoformat(),
                'status': 'active',
                'conversation_state': 'greeting'
            }
            
            # Build WebSocket URL (only ucid parameter like working Kogta project)
            ws_url = f'ws://43.205.216.106:8000/ws?ucid={call_id}'
            
            # Return XML response to connect to WebSocket
            response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<response>
    <start-record/>
    <stream is_sip='true' url='{ws_url}'>516473</stream>
</response>"""
            
            log.info(f"🔗 Connecting call {call_id} to WebSocket: {ws_url}")
            return Response(content=response_xml, media_type='text/xml')
            
        elif event == "Stream":
            log.info(f"📡 Stream event for call {call_id}")
            return Response(content="<hangup></hangup>", media_type='text/xml')
            
        elif event in ["Hangup", "Disconnect"]:
            log.info(f"📴 Call ended - UCID: {call_id}")
            if call_id in call_sessions:
                call_sessions[call_id]['status'] = 'ended'
                call_sessions[call_id]['end_time'] = datetime.now().isoformat()
            return Response(content="<response></response>", media_type='text/xml')
            
        else:
            log.info(f"❓ Unknown event: {event}")
            return Response(content="<response></response>", media_type='text/xml')
            
    except Exception as e:
        log.error(f"❌ Error in inbound hook: {e}")
        return Response(content="<response></response>", media_type='text/xml')

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, ucid: str = None, cid: str = None):
    """WebSocket endpoint for real-time voice processing
    Handles the actual conversation with interruption support"""
    
    if not ucid:
        ucid = str(id(websocket))
    
    log.info(f"🎙️ WebSocket connection - UCID: {ucid}, Caller: {cid}")
    
    try:
        await websocket.accept()
        log.info(f"✅ WebSocket accepted - UCID: {ucid}")
    except Exception as e:
        log.error(f"❌ WebSocket accept failed: {e}")
        return
    
    # Add to active connections
    connection_id = str(id(websocket))
    active_connections[connection_id] = websocket
    
    # Initialize services with error handling
    try:
        log.info("🔧 Initializing STT service...")
        stt_service = SarvamSTTService()
        log.info("✅ STT service initialized")
    except Exception as e:
        log.error(f"❌ STT service failed: {e}")
        await websocket.close()
        return
    
    try:
        log.info("🔧 Initializing TTS service...")
        tts_service = SarvamTTSService()
        log.info("✅ TTS service initialized")
    except Exception as e:
        log.error(f"❌ TTS service failed: {e}")
        await websocket.close()
        return
    
    try:
        log.info("🔧 Initializing conversation agent...")
        conversation_agent = ParcelTrackingAgent()
        log.info("✅ Conversation agent initialized")
    except Exception as e:
        log.error(f"❌ Conversation agent failed: {e}")
        await websocket.close()
        return
    
    try:
        log.info("🔧 Initializing Ozonetel service...")
        ozonetel_service = OzonetelService()
        log.info("✅ Ozonetel service initialized")
    except Exception as e:
        log.error(f"❌ Ozonetel service failed: {e}")
        await websocket.close()
        return
    
    # Setup transcription queues
    audio_queue = queue.Queue()
    result_queue = queue.Queue()
    
    # Start STT service
    stt_thread = threading.Thread(
        target=stt_service.run_stream,
        args=(audio_queue, result_queue, ucid)
    )
    stt_thread.start()
    
    # Initialize conversation state
    conversation_state = {
        'stage': 'greeting',
        'tracking_id': None,
        'customer_name': None,
        'language': 'English',
        'last_intent': None,
        'retry_count': 0
    }
    
    # Clear any stale interruption flags from previous calls
    interruption_manager.clear_interruption(ucid)
    log.info(f"🧹 Cleared any stale interruption flags for new call {ucid}")
    
    # Send initial greeting
    greeting_message = conversation_agent.generate_greeting_response()
    try:
        interruption_manager.set_agent_speaking(ucid, True, "speaking_greeting")
        
        # Generate and send greeting audio
        greeting_audio = tts_service.generate_speech(greeting_message, "en-IN")
        if greeting_audio:
            success = await AudioStreamer.stream_audio_with_interruption(websocket, greeting_audio, ucid)
            if not success:
                log.info("🛑 Greeting was interrupted")
        
        interruption_manager.set_agent_speaking(ucid, False, "greeting_completed")
        
    except Exception as e:
        log.error(f"Error sending greeting: {e}")
        interruption_manager.set_agent_speaking(ucid, False, "greeting_error")
    
    async def process_customer_speech():
        """Process customer speech and generate responses"""
        nonlocal conversation_state
        
        while True:
            try:
                # Get transcript from STT
                try:
                    result = result_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    if not stt_thread.is_alive():
                        break
                    continue
                
                # Extract transcript
                transcript_data = stt_service.get_final_transcript(result)
                transcript = transcript_data.get('transcript', '').strip()
                confidence = transcript_data.get('confidence', 0.0)
                
                if not transcript or len(transcript) < 2:
                    continue
                
                # Check for interruption
                if interruption_manager.detect_interruption(ucid, transcript, confidence):
                    log.info(f"🚨 INTERRUPTION DETECTED! Transcript: '{transcript}'")
                    # Stop any current audio
                    try:
                        await ozonetel_service.stop_audio_playback(ucid)
                    except Exception as e:
                        log.error(f"Error stopping audio: {e}")
                    continue
                
                log.info(f"📝 Customer: '{transcript}' (confidence: {confidence:.2f})")
                
                # Analyze customer input
                analysis = conversation_agent.analyze_customer_input(transcript, conversation_state)
                
                # Generate response based on analysis
                response_text = await handle_customer_intent(analysis, conversation_state, transcript)
                
                # Send response if we have one
                if response_text:
                    await send_agent_response(response_text)
                
                # Check if customer wants to end the call
                if conversation_state.get('should_hangup', False):
                    log.info(f"🔚 Customer requested call termination - hanging up call {ucid}")
                    await asyncio.sleep(2)  # Wait for goodbye message
                    
                    try:
                        caller_phone = call_sessions.get(ucid, {}).get('caller_id')
                        success = await ozonetel_service.hangup_call(ucid, caller_phone)
                        if success:
                            log.info(f"✅ Call {ucid} terminated successfully")
                    except Exception as e:
                        log.error(f"❌ Error terminating call {ucid}: {e}")
                    
                    await websocket.close()
                    break
                
            except Exception as e:
                log.error(f"Error processing customer speech: {e}")
                break
    
    async def handle_customer_intent(analysis: dict, conversation_state: dict, transcript: str) -> str:
        """Handle customer intent with improved conversation flow"""
        intent = analysis.get('intent', 'unclear')
        tracking_id = analysis.get('tracking_id', '').strip()
        current_stage = conversation_state.get('stage', 'greeting')
        
        # Track retry attempts
        if intent == 'unclear':
            conversation_state['retry_count'] = conversation_state.get('retry_count', 0) + 1
        else:
            conversation_state['retry_count'] = 0
        
        # Handle different intents based on conversation stage
        if intent == 'track_parcel':
            if tracking_id:
                conversation_state['tracking_id'] = tracking_id
                conversation_state['stage'] = 'providing_status'
                status_info = conversation_agent.get_parcel_status(tracking_id)
                conversation_state['stage'] = 'completed'
                return status_info
            else:
                conversation_state['stage'] = 'waiting_for_tracking_id'
                return conversation_agent.generate_tracking_request_response()
        
        elif intent == 'provide_tracking_id':
            if current_stage in ['waiting_for_tracking_id', 'greeting', 'listening']:
                conversation_state['tracking_id'] = tracking_id
                conversation_state['stage'] = 'providing_status'
                status_info = conversation_agent.get_parcel_status(tracking_id)
                conversation_state['stage'] = 'completed'
                return status_info
            else:
                return "I already have your tracking information. Is there anything else I can help you with?"
        
        elif intent == 'general_question':
            response = conversation_agent.handle_general_question(transcript, conversation_state)
            if current_stage == 'waiting_for_tracking_id':
                response += " But first, what's your tracking number?"
            return response
        
        elif intent == 'greeting':
            if 'thank' in transcript.lower() or 'thanks' in transcript.lower():
                conversation_state['stage'] = 'completed'
                return conversation_agent.generate_completion_response()
            else:
                if current_stage == 'greeting':
                    conversation_state['stage'] = 'listening'
                    return "Thanks for calling! I'm here to help you track your packages. Do you have a tracking number for me?"
                else:
                    return "How can I help you today? Do you need to track a package?"
        
        elif intent == 'end_call':
            log.info(f"🔚 Customer wants to end call: '{transcript}'")
            conversation_state['stage'] = 'ending'
            conversation_state['should_hangup'] = True
            return conversation_agent.generate_completion_response()
        
        elif intent == 'unclear':
            retry_count = conversation_state.get('retry_count', 0)
            if current_stage == 'waiting_for_tracking_id':
                if retry_count >= 3:
                    return "I'm having trouble understanding the tracking number. Could you try spelling it out letter by letter?"
                else:
                    return conversation_agent.generate_clarification_response(transcript) + " I'm looking for your tracking number."
            else:
                if retry_count >= 3:
                    return "I want to make sure I help you with the right thing. Are you looking to track a package?"
                else:
                    return conversation_agent.generate_clarification_response(transcript)
        
        # Default response
        return "I'm here to help you track your packages! Do you have a tracking number for me?"
    
    async def send_agent_response(response_text: str):
        """Send agent response with interruption handling"""
        try:
            interruption_manager.set_agent_speaking(ucid, True, "speaking_response")
            
            # Generate and send response audio
            audio_bytes = tts_service.generate_speech(response_text, "en-IN")
            if audio_bytes:
                success = await AudioStreamer.stream_audio_with_interruption(websocket, audio_bytes, ucid)
                if not success:
                    log.info("🛑 Agent response was interrupted")
            
            interruption_manager.set_agent_speaking(ucid, False, "response_completed")
            
        except Exception as e:
            log.error(f"Error sending response: {e}")
            interruption_manager.set_agent_speaking(ucid, False, "response_error")
    
    # Start speech processing
    speech_task = asyncio.create_task(process_customer_speech())
    
    try:
        # Handle incoming audio data
        while True:
            data = await websocket.receive()
            
            if 'text' in data:
                text_data = data['text']
                
                try:
                    json_data = json.loads(text_data)
                    
                    # Log media packets occasionally to reduce spam
                    if json_data.get('type') == 'media':
                        if not hasattr(websocket_endpoint, '_media_count'):
                            websocket_endpoint._media_count = 0
                        websocket_endpoint._media_count += 1
                        # Only log every 500th packet instead of every 100th
                        if websocket_endpoint._media_count % 500 == 1:
                            log.info(f"📋 Media packet #{websocket_endpoint._media_count}")
                    else:
                        log.info(f"📋 Non-media packet: type={json_data.get('type', 'unknown')}")
                    
                    if json_data.get('event') == 'stop':
                        log.info(f"📴 Call ended - UCID: {ucid}")
                        break
                    elif json_data.get('event') == 'start':
                        log.info(f"📞 Call started - UCID: {ucid}")
                        continue
                        
                except json.JSONDecodeError:
                    pass
                
                # Send audio to STT service
                audio_queue.put(text_data)
            else:
                log.warning(f"📭 Received WebSocket data without 'text' field: {data}")
                
    except WebSocketDisconnect:
        log.info(f"📴 WebSocket disconnected - UCID: {ucid}")
    except Exception as e:
        log.error(f"❌ WebSocket error: {e}")
    finally:
        log.info(f"🧹 Cleaning up connection for UCID: {ucid}")
        
        # Terminate call via Ozonetel
        try:
            caller_phone = call_sessions.get(ucid, {}).get('caller_id')
            termination_success = await ozonetel_service.hangup_call(ucid, caller_phone)
            if termination_success:
                log.info(f"✅ Call {ucid} terminated via Ozonetel")
        except Exception as e:
            log.warning(f"⚠️ Error terminating call {ucid}: {e}")
        
        # Stop STT
        audio_queue.put(None)
        
        # Cancel speech processing
        if not speech_task.done():
            speech_task.cancel()
        
        # Wait for STT thread
        if stt_thread.is_alive():
            stt_thread.join(timeout=5.0)
        
        # Remove from active connections
        if connection_id in active_connections:
            del active_connections[connection_id]
        
        # Update call session
        if ucid in call_sessions:
            call_sessions[ucid]['status'] = 'completed'
            call_sessions[ucid]['end_time'] = datetime.now().isoformat()
        
        log.info(f"✅ Cleanup completed for UCID: {ucid}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "📦 Parcel Tracking Voice Agent",
        "description": "Voice-based parcel tracking with interruption handling",
        "features": [
            "✅ Inbound call handling",
            "✅ Real-time voice processing", 
            "✅ Sarvam speech recognition",
            "✅ Sarvam text-to-speech",
            "✅ Ozonetel integration",
            "✅ Interruption handling (barge-in)",
            "✅ Parcel tracking simulation"
        ],
        "active_connections": len(active_connections),
        "active_calls": len([s for s in call_sessions.values() if s['status'] == 'active']),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/stats")
async def get_stats():
    """Get call statistics"""
    return {
        "active_connections": len(active_connections),
        "total_calls": len(call_sessions),
        "active_calls": len([s for s in call_sessions.values() if s['status'] == 'active']),
        "completed_calls": len([s for s in call_sessions.values() if s['status'] == 'completed']),
        "call_sessions": call_sessions,
        "timestamp": datetime.now().isoformat()
    }