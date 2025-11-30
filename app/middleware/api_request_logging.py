"""Middleware for logging API requests."""
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import ApiRequestLogRepository

logger = logging.getLogger(__name__)


class ApiRequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests to the database."""
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and log it."""
        # Call the next middleware/endpoint
        response = await call_next(request)
        
        # Log the request (async, don't block response)
        try:
            # Extract user_id if available from request state
            user_id = None
            if hasattr(request.state, "user") and request.state.user:
                user_id = request.state.user.get("id")
            
            # Get client IP
            ip_address = None
            if request.client:
                ip_address = request.client.host
            
            # Get payload summary for POST/PUT/PATCH requests
            payload_summary = None
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    # Note: request body has already been consumed, so we can't read it here
                    # For now, we'll just log the content type
                    content_type = request.headers.get("content-type", "")
                    payload_summary = json.dumps({"content_type": content_type})
                except Exception:
                    pass
            
            # Log to database
            ApiRequestLogRepository.log_request(
                user_id=user_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                ip_address=ip_address,
                payload_summary=payload_summary,
            )
        except Exception as e:
            # Don't break the app if logging fails
            logger.error(f"Failed to log API request: {e}")
        
        return response
