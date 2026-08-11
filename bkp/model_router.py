"""
Model Router - Intelligent model selection based on task type
Routes requests to appropriate Ollama models for optimal performance
"""

import re
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class ModelRouter:
    """
    Routes queries to appropriate models based on task complexity and type
    """
    
    # Model configurations
    MODELS = {
        "tool_calling": {
            "name": "llama3.1:8b",
            "description": "Best for tool calling and complex reasoning",
            "use_cases": ["order lookup", "return eligibility", "database queries"]
        },
        "rag": {
            "name": "llama3.2:3b",
            "description": "Efficient for RAG and document retrieval",
            "use_cases": ["policy questions", "shipping info", "general knowledge"]
        },
        "simple": {
            "name": "llama3.2:1b",
            "description": "Fast for simple queries",
            "use_cases": ["greetings", "simple questions", "clarifications"]
        }
    }
    
    # Keywords for task detection
    TOOL_KEYWORDS = [
        "order", "return", "refund", "eligibility", "status",
        "ORD-", "delivery", "purchase", "bought", "ordered"
    ]
    
    RAG_KEYWORDS = [
        "policy", "shipping", "how long", "what is", "explain",
        "tell me about", "information", "details", "rules"
    ]
    
    SIMPLE_KEYWORDS = [
        "hello", "hi", "hey", "thanks", "thank you", "bye",
        "yes", "no", "ok", "okay"
    ]
    
    def __init__(self, default_model: str = "llama3.2:3b"):
        """
        Initialize router with default model
        
        Args:
            default_model: Model to use when task type is unclear
        """
        self.default_model = default_model
        logger.info(f"ModelRouter initialized with default model: {default_model}")
    
    def detect_task_type(self, message: str) -> str:
        """
        Detect the type of task based on message content
        
        Args:
            message: User's message
            
        Returns:
            Task type: "tool_calling", "rag", or "simple"
        """
        message_lower = message.lower()
        
        # Check for simple queries first (fastest model)
        if any(keyword in message_lower for keyword in self.SIMPLE_KEYWORDS):
            if len(message.split()) <= 5:  # Short messages
                return "simple"
        
        # Check for tool calling needs (most capable model)
        if any(keyword in message_lower for keyword in self.TOOL_KEYWORDS):
            return "tool_calling"
        
        # Check for RAG needs (balanced model)
        if any(keyword in message_lower for keyword in self.RAG_KEYWORDS):
            return "rag"
        
        # Default to RAG for general questions
        return "rag"
    
    def select_model(self, message: str) -> Tuple[str, str, Dict]:
        """
        Select the best model for the given message
        
        Args:
            message: User's message
            
        Returns:
            Tuple of (model_name, task_type, model_info)
        """
        task_type = self.detect_task_type(message)
        model_info = self.MODELS.get(task_type, self.MODELS["rag"])
        model_name = model_info["name"]
        
        logger.info(f"Selected model '{model_name}' for task type '{task_type}'")
        logger.debug(f"Message: {message[:50]}...")
        
        return model_name, task_type, model_info
    
    def get_model_stats(self) -> Dict:
        """
        Get statistics about available models
        
        Returns:
            Dictionary with model information
        """
        return {
            "available_models": list(self.MODELS.keys()),
            "default_model": self.default_model,
            "models": self.MODELS
        }
    
    def explain_selection(self, message: str) -> str:
        """
        Explain why a particular model was selected
        
        Args:
            message: User's message
            
        Returns:
            Explanation string
        """
        model_name, task_type, model_info = self.select_model(message)
        
        explanation = f"""
Model Selection:
- Selected: {model_name}
- Task Type: {task_type}
- Reason: {model_info['description']}
- Use Cases: {', '.join(model_info['use_cases'])}
"""
        return explanation.strip()


# Example usage
if __name__ == "__main__":
    router = ModelRouter()
    
    # Test cases
    test_messages = [
        "What's the status of order ORD-2024-001?",
        "What is your return policy?",
        "Hello, how are you?",
        "Can I return my laptop?",
        "How long does shipping take?",
    ]
    
    print("Model Router Test Cases:\n")
    for msg in test_messages:
        model, task, info = router.select_model(msg)
        print(f"Message: {msg}")
        print(f"  → Model: {model} (Task: {task})")
        print(f"  → Reason: {info['description']}\n")

# Made with Bob
