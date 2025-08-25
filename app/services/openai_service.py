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
    
    async def get_bible_answer(self, question: str) -> str:
        """Get an AI-generated answer to a Bible-related question."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "You are a helpful Bible scholar with deep knowledge of Christian theology, "
                            "biblical history, and scriptural interpretation. Provide thoughtful, accurate, "
                            "and biblically-grounded answers. When appropriate, include relevant scripture "
                            "references. Be respectful of different denominational perspectives."
                        )
                    },
                    {"role": "user", "content": question}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise Exception(f"Failed to get AI response: {str(e)}")
