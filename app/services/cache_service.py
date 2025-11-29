"""Redis caching service for Bible Q&A application."""
import hashlib
import json
import logging
from typing import Any, Optional

import redis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global Redis client
_redis_client: Optional[redis.Redis] = None


def initialize_redis() -> None:
    """Initialize the Redis client."""
    global _redis_client
    
    if _redis_client is not None:
        logger.warning("Redis client already initialized")
        return
    
    settings = get_settings()
    
    if not settings.cache_enabled:
        logger.info("Caching is disabled in settings")
        return
    
    try:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        # Test connection
        _redis_client.ping()
        logger.info(f"Redis client initialized: {settings.redis_url}")
    except RedisError as e:
        logger.error(f"Failed to initialize Redis client: {e}")
        _redis_client = None
        # Don't raise - degrade gracefully without cache


def close_redis() -> None:
    """Close the Redis client connection."""
    global _redis_client
    
    if _redis_client is not None:
        try:
            _redis_client.close()
            logger.info("Redis client closed")
        except RedisError as e:
            logger.error(f"Error closing Redis client: {e}")
        finally:
            _redis_client = None


def _get_client() -> Optional[redis.Redis]:
    """Get the Redis client if available."""
    return _redis_client


def _generate_cache_key(prefix: str, *args: Any) -> str:
    """Generate a cache key from prefix and arguments.
    
    Args:
        prefix: Key prefix (e.g., 'verse', 'question', 'search')
        *args: Values to include in the key
        
    Returns:
        Cache key string
    """
    # Normalize arguments to strings
    normalized = []
    for arg in args:
        if isinstance(arg, str):
            normalized.append(arg.lower().strip())
        elif isinstance(arg, (dict, list)):
            normalized.append(json.dumps(arg, sort_keys=True))
        else:
            normalized.append(str(arg))
    
    # Create hash of normalized arguments for consistent key length
    content = ":".join(normalized)
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    return f"{prefix}:{content_hash}"


class CacheService:
    """Service for caching Bible verses, questions, and search results."""
    
    @staticmethod
    def get(key: str) -> Optional[Any]:
        """Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or error
        """
        client = _get_client()
        if client is None:
            return None
        
        try:
            value = client.get(key)
            if value is None:
                logger.info(f"Cache miss for key: {key[:50]}...")
                return None
            
            logger.info(f"Cache hit for key: {key[:50]}...")
            
            # Try to parse as JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
                
        except RedisError as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    @staticmethod
    def set(key: str, value: Any, ttl: int = 0) -> bool:
        """Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (0 = no expiry)
            
        Returns:
            True if successful, False otherwise
        """
        client = _get_client()
        if client is None:
            return False
        
        try:
            # Serialize value as JSON
            if isinstance(value, (dict, list)):
                serialized = json.dumps(value)
            else:
                serialized = str(value)
            
            if ttl > 0:
                client.setex(key, ttl, serialized)
            else:
                client.set(key, serialized)
            
            return True
            
        except RedisError as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """Delete a key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        client = _get_client()
        if client is None:
            return False
        
        try:
            client.delete(key)
            return True
        except RedisError as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    @staticmethod
    def clear_pattern(pattern: str) -> int:
        """Clear all keys matching a pattern.
        
        Args:
            pattern: Key pattern (e.g., 'question:*')
            
        Returns:
            Number of keys deleted
        """
        client = _get_client()
        if client is None:
            return 0
        
        try:
            keys = client.keys(pattern)
            if keys:
                return client.delete(*keys)
            return 0
        except RedisError as e:
            logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return 0
    
    # Convenience methods for specific cache types
    
    @staticmethod
    def get_verse(reference: str) -> Optional[dict]:
        """Get cached verse by reference."""
        key = _generate_cache_key("verse", reference)
        return CacheService.get(key)
    
    @staticmethod
    def set_verse(reference: str, verse_data: dict) -> bool:
        """Cache a verse (no expiry for static Bible content)."""
        settings = get_settings()
        key = _generate_cache_key("verse", reference)
        return CacheService.set(key, verse_data, ttl=settings.cache_ttl_verses)
    
    @staticmethod
    def get_passage(book: str, chapter: int, start_verse: int, end_verse: int) -> Optional[list]:
        """Get cached passage."""
        key = _generate_cache_key("passage", book, chapter, start_verse, end_verse)
        return CacheService.get(key)
    
    @staticmethod
    def set_passage(book: str, chapter: int, start_verse: int, end_verse: int, passage_data: list) -> bool:
        """Cache a passage (no expiry for static Bible content)."""
        settings = get_settings()
        key = _generate_cache_key("passage", book, chapter, start_verse, end_verse)
        return CacheService.set(key, passage_data, ttl=settings.cache_ttl_verses)
    
    @staticmethod
    def get_chapter(book: str, chapter: int) -> Optional[dict]:
        """Get cached chapter."""
        key = _generate_cache_key("chapter", book, chapter)
        return CacheService.get(key)
    
    @staticmethod
    def set_chapter(book: str, chapter: int, chapter_data: dict) -> bool:
        """Cache a chapter (no expiry for static Bible content)."""
        settings = get_settings()
        key = _generate_cache_key("chapter", book, chapter)
        return CacheService.set(key, chapter_data, ttl=settings.cache_ttl_verses)
    
    @staticmethod
    def get_search(keyword: str, limit: int) -> Optional[list]:
        """Get cached search results."""
        key = _generate_cache_key("search", keyword, limit)
        return CacheService.get(key)
    
    @staticmethod
    def set_search(keyword: str, limit: int, results: list) -> bool:
        """Cache search results (1 hour TTL)."""
        settings = get_settings()
        key = _generate_cache_key("search", keyword, limit)
        return CacheService.set(key, results, ttl=settings.cache_ttl_searches)
    
    @staticmethod
    def get_question(question: str, conversation_history: Optional[list] = None) -> Optional[str]:
        """Get cached answer for a question.
        
        Args:
            question: The question text
            conversation_history: Optional conversation context
            
        Returns:
            Cached answer or None
        """
        # Include conversation history in cache key for context-aware caching
        key = _generate_cache_key("question", question, conversation_history or [])
        logger.info(f"Looking up question cache with key: {key}")
        result = CacheService.get(key)
        logger.info(f"Question cache result: {'HIT' if result else 'MISS'}")
        return result
    
    @staticmethod
    def set_question(question: str, answer: str, conversation_history: Optional[list] = None) -> bool:
        """Cache an answer for a question (24 hour TTL).
        
        Args:
            question: The question text
            answer: The answer to cache
            conversation_history: Optional conversation context
            
        Returns:
            True if cached successfully
        """
        settings = get_settings()
        key = _generate_cache_key("question", question, conversation_history or [])
        logger.info(f"Setting question cache with key: {key}")
        success = CacheService.set(key, answer, ttl=settings.cache_ttl_questions)
        logger.info(f"Question cache set: {'SUCCESS' if success else 'FAILED'}")
        return success


def get_cache_service() -> CacheService:
    """Dependency injector for cache service."""
    return CacheService()
