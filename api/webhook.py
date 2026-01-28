"""
Ozonetel webhook handlers
Clean implementation for call management
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from services.ozonetel import OzonetelService
from services.sarvam_stt import SarvamSTTService
from services.sarvam_tts import SarvamTTSService
from services.conversation import ParcelTrackingAgent, ConversationState
from core.interruption import interruption_manager
from core.audio_streaming import AudioStreamer

import asyncio
import queue
import threading
import json

log = logging.getLogger(__name__)

class WebhookHandler:
    """
    Clean webhook handler for Ozonetel integration
    """
    
    def __init__(self):
        self.ozonetel_service = OzonetelService()
        self.active_calls: Dict[str, Dict] = {}
    
    async def handle_inbound_call(
        self,
        request: Request,
        event: str = None,
        sid: str = None,
        ucid: str = None,
        cid: str = None,
        cid_e164: str = None,
        called_number: str = None
    ) -> Response:
        """
        Handle inbound call webhook from Ozonetel
        """
        try:
            call_id = sid or ucid or "unknown"
            caller_id = cid or cid_e164 or "unknown"
            
            log.info(f"📞 Inbound call - Event: {event}, UCID: {call_id}, Caller: {caller_id}")
            
            if event == "NewCall" or event is None:
                # Create call session
                self.active_calls[call_id] = {
                    'call_id': call_id,
                    'caller_id': caller_id,
                    'start_time': datetime.now().isoformat(),
                    'status': 'active',
                    'conversation_state': ConversationState()
                }
                
                # Generate XML response to connect to WebSocket
                response_xml = self.ozonetel_service.get_webhook_response(call_id, caller_id)
                
                log.info(f"🔗 Connecting call {call_id} to WebSocket")
                return Response(content=response_xml, media_type='text/xml')
            
            elif event == "Stream":
                log.info(f"📡 Stream event for call {call_id}")
                return Response(content="<hangup></hangup>", media_type='text/xml')
            
            elif event in ["Hangup", "Disconnect"]:
                log.info(f"📴 Call ended - UCID: {call_id}")
                if call_id in self.active_calls:
                    self.active_calls[call_id]['status'] = 'ended'
                    self.active_calls[call_id]['end_time'] = datetime.now().isoformat()
                return Response(content="<response></response>", media_type='text/xml')
            
            else:
                log.info(f"❓ Unknown event: {event}")
                return Response(content="<response></response>", media_type='text/xml')
            
        except Exception as e:
            log.error(f"❌ Error in inbound hook: {e}")
            return Response(content="<response></response>", media_type='text/xml')
    
    async def handle_websocket_connection(self, websocket: WebSocket, ucid: str = None, cid: str = None):
        """
        Handle WebSocket connection for real-time voice processing - SIMPLIFIED FOR DEBUGGING
        """
        if not ucid:
            ucid = str(id(websocket))
        
        log.info(f"🎙️ WebSocket connection attempt - UCID: {ucid}, Caller: {cid}")
        
        try:
            # Accept WebSocket connection
            await websocket.accept()
            log.info(f"✅ WebSocket accepted successfully - UCID: {ucid}")
            
            # Send immediate confirmation to Ozonetel
            try:
                await websocket.send_text(json.dumps({
                    "type": "connection_established",
                    "ucid": ucid,
                    "status": "ready"
                }))
                log.info(f"📡 Sent connection confirmation for {ucid}")
            except Exception as e:
                log.warning(f"⚠️ Could not send connection confirmation: {e}")
            
            # Keep connection alive for testing
            log.info(f"🔄 Keeping WebSocket connection alive for {ucid}")
            
            # Simple message loop to keep connection alive
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                    log.info(f"📥 Received data from Ozonetel for {ucid}: {str(data)[:100]}...")
                    
                    if 'text' in data:
                        text_data = data['text']
                        try:
                            json_data = json.loads(text_data)
                            if json_data.get('event') == 'stop':
                                log.info(f"📴 Received stop event for {ucid}")
                                break
                            elif json_data.get('event') == 'start':
                                log.info(f"📞 Received start event for {ucid}")
                        except json.JSONDecodeError:
                            pass
                    
                except asyncio.TimeoutError:
                    log.info(f"⏰ WebSocket timeout for {ucid} - sending ping")
                    try:
                        await websocket.ping()
                    except:
                        log.error(f"❌ WebSocket ping failed for {ucid}")
                        break
                        
                except WebSocketDisconnect:
                    log.info(f"📴 WebSocket disconnected for {ucid}")
                    break
                    
                except Exception as e:
                    log.error(f"❌ WebSocket error for {ucid}: {e}")
                    break
            
        except Exception as e:
            log.error(f"❌ WebSocket connection failed for {ucid}: {e}")
            try:
                await websocket.close(code=1011, reason=f"Server error: {str(e)}")
            except:
                pass
        finally:
            log.info(f"🧹 WebSocket connection ended for {ucid}")
    
    async def _handle_audio_stream(self, websocket: WebSocket, audio_queue: queue.Queue, ucid: str):
        """Handle incoming audio stream from Ozonetel with improved error handling"""
        try:
            log.info(f"🎧 Starting audio stream handler for {ucid}")
            
            while True:
                try:
                    # Wait for data with timeout to prevent hanging
                    data = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                    
                    if 'text' in data:
                        text_data = data['text']
                        
                        # Handle JSON control messages
                        try:
                            json_data = json.loads(text_data)
                            
                            if json_data.get('event') == 'stop':
                                log.info(f"📴 Received stop event for {ucid}")
                                break
                            elif json_data.get('event') == 'start':
                                log.info(f"📞 Received start event for {ucid}")
                                continue
                            elif json_data.get('type') == 'media':
                                # This is audio data
                                audio_queue.put(text_data)
                                continue
                                
                        except json.JSONDecodeError:
                            # Not JSON, treat as raw audio data
                            audio_queue.put(text_data)
                    
                    elif 'bytes' in data:
                        # Handle binary audio data
                        audio_queue.put(data['bytes'])
                    
                    # Check for interruption
                    if interruption_manager.is_interrupted(ucid):
                        log.info(f"🚨 INTERRUPTION DETECTED - Emergency stop for {ucid}")
                        await AudioStreamer.emergency_stop_audio(ucid)
                        
                        # Try to stop audio playback on Ozonetel
                        try:
                            await self.ozonetel_service.stop_audio_playback(ucid)
                        except Exception as e:
                            log.error(f"Error stopping Ozonetel audio: {e}")
                
                except asyncio.TimeoutError:
                    log.warning(f"⏰ Audio stream timeout for {ucid} - checking connection")
                    # Send ping to check if connection is still alive
                    try:
                        await websocket.ping()
                        continue
                    except:
                        log.error(f"❌ WebSocket connection lost for {ucid}")
                        break
                        
                except WebSocketDisconnect:
                    log.info(f"📴 WebSocket disconnected during audio stream for {ucid}")
                    break
                    
                except Exception as e:
                    log.error(f"❌ Error in audio stream for {ucid}: {e}")
                    # Don't break on individual errors, continue processing
                    continue
        
        except Exception as e:
            log.error(f"❌ Fatal error in audio stream handler for {ucid}: {e}")
        finally:
            log.info(f"🔚 Audio stream handler ended for {ucid}")
    
    async def _process_customer_speech(
        self, result_queue, stt_service, tts_service, conversation_agent, 
        conversation_state, websocket, ucid, stt_thread
    ):
        """Process customer speech and generate responses"""
        try:
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
                    
                    log.info(f"📝 Customer: '{transcript}' (confidence: {confidence:.2f})")
                    
                    # Analyze customer input
                    analysis = conversation_agent.analyze_customer_input(transcript, conversation_state)
                    log.info(f"🧠 Analysis: {analysis}")
                    
                    # Generate response based on analysis
                    response_text = await self._generate_response(
                        analysis, conversation_state, conversation_agent, transcript
                    )
                    
                    # Send response to customer
                    if response_text:
                        try:
                            # Clear any previous interruption flag before speaking
                            interruption_manager.clear_interruption(ucid)
                            
                            success = await tts_service.speak_with_interruption(websocket, response_text, ucid)
                            
                            if not success:
                                log.info("🛑 Agent response was interrupted")
                                
                        except Exception as e:
                            log.error(f"Error sending response: {e}")
                
                except Exception as e:
                    log.error(f"Error processing customer speech: {e}")
                    break
        
        except Exception as e:
            log.error(f"Error in speech processing: {e}")
    
    async def _generate_response(self, analysis, conversation_state, conversation_agent, transcript) -> str:
        """Generate appropriate response based on analysis"""
        try:
            intent = analysis.get('intent', 'unclear')
            
            if intent == 'track_parcel':
                if conversation_state.stage == 'greeting':
                    conversation_state.stage = 'waiting_for_tracking_id'
                    return conversation_agent.generate_tracking_request_response()
            
            elif intent == 'provide_tracking_id':
                if conversation_state.stage == 'waiting_for_tracking_id':
                    tracking_id = analysis.get('tracking_id', transcript.strip())
                    conversation_state.tracking_id = tracking_id
                    conversation_state.stage = 'providing_status'
                    
                    status_info = conversation_agent.get_parcel_status(tracking_id)
                    conversation_state.stage = 'completed'
                    return status_info
                else:
                    return conversation_agent.generate_tracking_request_response()
            
            elif intent == 'general_question':
                return conversation_agent.handle_general_question(transcript, conversation_state)
            
            elif intent == 'greeting':
                if 'thank' in transcript.lower():
                    conversation_state.stage = 'completed'
                    return conversation_agent.generate_completion_response()
                else:
                    conversation_state.stage = 'listening'
                    return conversation_agent.generate_greeting_response()
            
            elif intent == 'unclear':
                return conversation_agent.generate_clarification_response(transcript)
            
            else:
                return "I'm here to help you track your packages! Do you have a tracking number for me?"
        
        except Exception as e:
            log.error(f"Error generating response: {e}")
            return "I'm sorry, I'm having trouble right now. Could you try again?"
    
    async def _cleanup_call(self, ucid: str, stt_thread: threading.Thread):
        """Cleanup call resources"""
        try:
            log.info(f"🧹 Cleaning up call {ucid}")
            
            # Terminate call via Ozonetel
            try:
                caller_phone = self.active_calls.get(ucid, {}).get('caller_id')
                await self.ozonetel_service.hangup_call(ucid, caller_phone)
            except Exception as e:
                log.warning(f"⚠️ Error terminating call {ucid}: {e}")
            
            # Wait for STT thread
            if stt_thread.is_alive():
                stt_thread.join(timeout=5.0)
            
            # Update call session
            if ucid in self.active_calls:
                self.active_calls[ucid]['status'] = 'completed'
                self.active_calls[ucid]['end_time'] = datetime.now().isoformat()
            
            # Cleanup interruption handler
            interruption_manager.end_call(ucid)
            
            log.info(f"✅ Cleanup completed for {ucid}")
        
        except Exception as e:
            log.error(f"Error in cleanup: {e}")
    
    def get_stats(self) -> Dict:
        """Get call statistics"""
        return {
            "active_calls": len([c for c in self.active_calls.values() if c['status'] == 'active']),
            "total_calls": len(self.active_calls),
            "completed_calls": len([c for c in self.active_calls.values() if c['status'] == 'completed']),
            "call_sessions": self.active_calls,
            "timestamp": datetime.now().isoformat()
        }