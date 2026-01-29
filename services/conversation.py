"""
Conversation Agent for parcel tracking
Simplified implementation with fallback support
"""

import logging
import random
from typing import Dict, Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)

@dataclass
class ConversationState:
    """State for conversation tracking"""
    stage: str = 'greeting'  # greeting -> listening -> tracking -> completed
    tracking_id: Optional[str] = None
    customer_name: Optional[str] = None
    language: str = 'English'

class ParcelTrackingAgent:
    """
    Parcel tracking conversation agent with fallback responses
    """
    
    def __init__(self):
        pass  # Simplified initialization
    
    def generate_greeting_response(self) -> str:
        """Generate a natural greeting"""
        greetings = [
            "Hello! Welcome to our parcel tracking service. How can I help you today?",
            "Hi there! I'm here to help you track your packages. What can I do for you?",
            "Good day! This is your parcel tracking assistant. How may I assist you?",
            "Hello! I can help you check the status of your parcels. What would you like to track?"
        ]
        return random.choice(greetings)
    
    def analyze_customer_input(self, transcript: str, conversation_state: ConversationState) -> Dict:
        """Analyze customer input and determine intent"""
        return self._fallback_analyze_input(transcript, conversation_state)
    
    def _fallback_analyze_input(self, transcript: str, conversation_state: ConversationState) -> Dict:
        """Simple fallback analysis"""
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
        
        # Check for end call
        if any(word in transcript_lower for word in ['bye', 'goodbye', 'end', 'hang up', 'call back']):
            return {
                "intent": "end_call",
                "tracking_id": "",
                "confidence": 0.8,
                "reasoning": "Customer wants to end call"
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
        return random.choice(statuses)
    
    def generate_clarification_response(self, transcript: str) -> str:
        """Generate clarification response"""
        responses = [
            "I'm sorry, I didn't quite catch that. Could you repeat your tracking number?",
            "I didn't understand that clearly. Can you say that again?",
            "Could you please repeat that? I want to make sure I help you correctly.",
            "I'm having trouble understanding. Could you speak a bit more clearly?"
        ]
        return random.choice(responses)
    
    def generate_completion_response(self) -> str:
        """Generate conversation completion response"""
        responses = [
            "You're welcome! Have a great day and thank you for using our service!",
            "Happy to help! Is there anything else you need assistance with?",
            "Glad I could help you track your package. Have a wonderful day!",
            "You're all set! Thanks for calling and have a great day!"
        ]
        return random.choice(responses)
    
    def handle_general_question(self, transcript: str, conversation_state: ConversationState) -> str:
        """Handle general questions"""
        return "I'm here to help you track packages. Do you have a tracking number I can look up for you?"