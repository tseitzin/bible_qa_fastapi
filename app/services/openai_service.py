"""OpenAI service for handling AI completions."""
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI API."""
    
    def __init__(self):
        from app.config import get_settings
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    async def get_bible_answer(self, question: str, conversation_history: list = None) -> str:
        """Get an AI-generated answer to a Bible-related question.
        
        Args:
            question: The user's question
            conversation_history: Optional list of previous messages in format:
                [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        
        Returns:
            The AI-generated answer
        """
        try:
            # Build messages array
            messages = [
                {
                    "role": "system", 
                    "content": (
                        "You are a helpful Bible scholar with deep knowledge of Christian theology, "
                        "biblical history, and scriptural interpretation. Provide thoughtful, accurate, "
                        "and biblically-grounded answers. When appropriate, include relevant scripture "
                        "references. Be respectful of different denominational perspectives. "
                        "When answering follow-up questions, maintain context from the previous conversation "
                        "and provide deeper insights or additional details as requested."
                    )
                }
            ]
            
            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add the current question
            messages.append({"role": "user", "content": question})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise Exception(f"Failed to get AI response: {str(e)}")
