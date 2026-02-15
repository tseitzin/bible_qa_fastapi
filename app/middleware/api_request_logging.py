"""Middleware for logging API requests."""
import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.database import ApiRequestLogRepository
from app.services.geolocation_service import GeolocationService
from app.utils.network import get_client_ip

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

            # Get client IP (handle proxy/load balancer)
            ip_address = get_client_ip(request)

            # Lookup geolocation for the IP (async, don't block)
            geolocation = None
            if ip_address and not ip_address.startswith('10.'):
                try:
                    geolocation = await GeolocationService.lookup_ip(ip_address)
                except Exception as geo_error:
                    logger.debug(f"Geolocation lookup failed: {geo_error}")

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
                country_code=geolocation.get('country_code') if geolocation else None,
                country_name=geolocation.get('country_name') if geolocation else None,
                city=geolocation.get('city') if geolocation else None,
            )
        except Exception as e:
            # Don't break the app if logging fails
            logger.error(f"Failed to log API request: {e}")

        return response
