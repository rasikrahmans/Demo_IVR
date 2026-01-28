"""
Conversation Agent using Strands for parcel tracking
Clean implementation with fallback support
"""

import logging
import random
from typing import Dict, Optional
from dataclasses import dataclass

from config import Config

log = logging.getLogger(__name__)

# Try to import Strands, fallback if not available
try:
    from strands import Agent
    from strands.models import BedrockModel
    STRANDS_AVAILABLE = True
    log.info("✅ Strands package imported successfully")
except ImportError as e:
    Agent = None
    BedrockModel = None
    STRANDS_AVAILABLE = False
    log.info(f"⚠️ Strands not available, using fallback mode: {e}")
except Exception as e:
    Agent = None
    BedrockModel = None
    STRANDS_AVAILABLE = False
    log.warning(f"⚠️ Strands import failed, using fallback mode: {e}")

@dataclass
class ConversationState:
    """State for conversation tracking"""
    stage: str = 'greeting'  # greeting -> listening -> tracking -> completed
    tracking_id: Optional[str] = None
    customer_name: Optional[str] = None
    language: str = 'English'

class ParcelTrackingAgent:
    """
    Clean parcel tracking conversation agent with Strands integration
    """
    
    def __init__(self):
        self.strands_agent = None
        
        if STRANDS_AVAILABLE and Config.AWS_ACCESS_KEY_ID:
            try:
                # Initialize Strands agent with Bedrock
                bedrock_model = BedrockModel(
                    model_id=Config.BEDROCK_MODEL_ID,
                    temperature=Config.BEDROCK_TEMPERATURE,
                    region=Config.AWS_REGION
                )
                
                self.strands_agent = Agent(
                    name="ParcelTrackingAgent",
                    model=bedrock_model,
                    instructions=self._get_agent_instructions()
                )
                
                log.info("✅ Strands agent initialized successfully")
                
            except Exception as e:
                log.warning(f"⚠️ Failed to initialize Strands agent: {e}")
                self.strands_agent = None
        else:
            log.info("ℹ️ Using fallback conversation mode (no Strands)")
    
    def _get_agent_instructions(self) -> str:
        """Get instructions for the Strands agent"""
        return """
        You are a helpful parcel tracking assistant for a voice-based IVR system.
        
        Your role:
        - Help customers track their parcels
        - Provide clear, concise responses suitable for voice interaction
        - Be friendly and professional
        - Keep responses short (1-2 sentences max)
        
        Guidelines:
        - Always speak naturally as if talking to someone on the phone
        - Ask for tracking numbers when needed
        - Provide realistic tracking updates
        - Handle interruptions gracefully
        - End conversations politely when tracking is complete
        
        Remember: This is a voice conversation, so keep responses conversational and brief.
        """
    
    def generate_greeting_response(self) -> str:
        """Generate a natural greeting"""
        greetings = [
            "Hello! Welcome to our parcel tracking service. How can I help you today?",
            "Hi there! I'm here to help you track your packages. What can I do for you?",
            "Good day! This is your parcel tracking assistant. How may I assist you?",
            "Hello! I can help you check the status of your parcels. What would you like to track?"
        ]
        
        if self.strands_agent:
            try:
                response = self.strands_agent.run("Generate a friendly greeting for a parcel tracking service")
                return response.strip()
            except Exception as e:
                log.warning(f"Strands greeting failed, using fallback: {e}")
        
        return random.choice(greetings)
    
    def analyze_customer_input(self, transcript: str, conversation_state: ConversationState) -> Dict:
        """Analyze customer input and determine intent"""
        
        if self.strands_agent:
            try:
                prompt = f"""
                Analyze this customer input for a parcel tracking service: "{transcript}"
                
                Current conversation stage: {conversation_state.stage}
                
                Determine the intent and extract any tracking information.
                Respond with JSON format:
                {{
                    "intent": "track_parcel|provide_tracking_id|general_question|greeting|unclear",
                    "tracking_id": "extracted_tracking_id_if_any",
                    "confidence": 0.0-1.0,
                    "reasoning": "brief_explanation"
                }}
                """
                
                response = self.strands_agent.run(prompt)
                
                # Try to parse JSON response
                import json
                try:
                    return json.loads(response)
                except:
                    # Fallback if JSON parsing fails
                    pass
                    
            except Exception as e:
                log.warning(f"Strands analysis failed, using fallback: {e}")
        
        # Fallback analysis
        return self._fallback_analyze_input(transcript, conversation_state)
    
    def _fallback_analyze_input(self, transcript: str, conversation_state: ConversationState) -> Dict:
        """Simple fallback analysis without Strands"""
        transcript_lower = transcript.lower().strip()
        
        # Check for tracking intent
        if any(word in transcript_lower for word in ['track', 'package', 'parcel', 'order', 'delivery']):
            return {
                "intent": "track_parcel",
                "tracking_id": "",
                "confidence": 0.8,
                "reasoning": "Contains tracking-related keywords"
            }
        
        # Check for tracking ID (simple pattern matching)
        import re
        tracking_patterns = [
            r'\b[A-Z0-9]{8,15}\b',  # Alphanumeric tracking codes
            r'\b\d{10,15}\b'        # Numeric tracking codes
        ]
        
        for pattern in tracking_patterns:
            match = re.search(pattern, transcript.upper())
            if match:
                return {
                    "intent": "provide_tracking_id",
                    "tracking_id": match.group(),
                    "confidence": 0.9,
                    "reasoning": "Found tracking ID pattern"
                }
        
        # Check for greetings
        if any(word in transcript_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            return {
                "intent": "greeting",
                "tracking_id": "",
                "confidence": 0.7,
                "reasoning": "Contains greeting words"
            }
        
        # Default to unclear
        return {
            "intent": "unclear",
            "tracking_id": "",
            "confidence": 0.3,
            "reasoning": "Could not determine clear intent"
        }
    
    def generate_tracking_request_response(self) -> str:
        """Generate response asking for tracking ID"""
        responses = [
            "I can help you track your package. What's your tracking number?",
            "Sure! Please provide your tracking ID so I can check the status.",
            "I'd be happy to track that for you. Can you give me the tracking number?",
            "Of course! What's the tracking number for your package?"
        ]
        
        if self.strands_agent:
            try:
                response = self.strands_agent.run("Ask the customer for their tracking number in a friendly way")
                return response.strip()
            except Exception as e:
                log.warning(f"Strands tracking request failed, using fallback: {e}")
        
        return random.choice(responses)
    
    def get_parcel_status(self, tracking_id: str) -> str:
        """Get parcel status (simulated for demo)"""
        
        # Simulate different tracking statuses
        statuses = [
            f"Great news! Your package {tracking_id} is out for delivery and should arrive today.",
            f"Your package {tracking_id} is currently in transit and will be delivered tomorrow.",
            f"Package {tracking_id} has been shipped and is on its way to you. Expected delivery is in 2-3 days.",
            f"Your order {tracking_id} is being prepared for shipment and will be dispatched soon.",
            f"Package {tracking_id} has arrived at the local facility and will be delivered shortly."
        ]
        
        if self.strands_agent:
            try:
                prompt = f"Provide a realistic tracking update for package {tracking_id}. Keep it brief and natural for voice."
                response = self.strands_agent.run(prompt)
                return response.strip()
            except Exception as e:
                log.warning(f"Strands status failed, using fallback: {e}")
        
        return random.choice(statuses)
    
    def generate_clarification_response(self, transcript: str) -> str:
        """Generate clarification response"""
        responses = [
            "I'm sorry, I didn't quite catch that. Could you repeat your tracking number?",
            "I didn't understand that clearly. Can you say that again?",
            "Could you please repeat that? I want to make sure I help you correctly.",
            "I'm having trouble understanding. Could you speak a bit more clearly?"
        ]
        
        if self.strands_agent:
            try:
                prompt = f"The customer said '{transcript}' but it wasn't clear. Ask for clarification politely."
                response = self.strands_agent.run(prompt)
                return response.strip()
            except Exception as e:
                log.warning(f"Strands clarification failed, using fallback: {e}")
        
        return random.choice(responses)
    
    def generate_completion_response(self) -> str:
        """Generate conversation completion response"""
        responses = [
            "You're welcome! Have a great day and thank you for using our service!",
            "Happy to help! Is there anything else you need assistance with?",
            "Glad I could help you track your package. Have a wonderful day!",
            "You're all set! Thanks for calling and have a great day!"
        ]
        
        if self.strands_agent:
            try:
                response = self.strands_agent.run("End the conversation politely after helping with parcel tracking")
                return response.strip()
            except Exception as e:
                log.warning(f"Strands completion failed, using fallback: {e}")
        
        return random.choice(responses)
    
    def handle_general_question(self, transcript: str, conversation_state: ConversationState) -> str:
        """Handle general questions"""
        if self.strands_agent:
            try:
                prompt = f"""
                Customer asked: "{transcript}"
                
                Respond helpfully but redirect to parcel tracking if appropriate.
                Keep response brief and conversational for voice interaction.
                """
                response = self.strands_agent.run(prompt)
                return response.strip()
            except Exception as e:
                log.warning(f"Strands general question failed, using fallback: {e}")
        
        return "I'm here to help you track packages. Do you have a tracking number I can look up for you?"