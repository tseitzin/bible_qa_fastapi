"""Page analytics router for tracking user behavior."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import get_current_admin_user, get_current_user_optional_dependency
from app.database import PageAnalyticsRepository
from app.models.schemas import ClickEventRequest, PageMetricsUpdate, PageViewRequest
from app.services.geolocation_service import GeolocationService
from app.utils.network import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.post("/page-view")
async def log_page_view(
    page_view: PageViewRequest,
    request: Request,
    current_user: Optional[dict] = Depends(get_current_user_optional_dependency)
):
    """Log a page view event."""
    try:
        # Get user ID if authenticated
        user_id = current_user.get("id") if current_user else None

        # Get client IP
        ip_address = get_client_ip(request)

        # Get user agent
        user_agent = request.headers.get("user-agent")

        # Lookup geolocation
        geolocation = None
        if ip_address and not ip_address.startswith('10.'):
            try:
                geolocation = await GeolocationService.lookup_ip(ip_address)
            except Exception as geo_error:
                logger.debug(f"Geolocation lookup failed: {geo_error}")

        # Log to database
        page_analytics_id = PageAnalyticsRepository.log_page_view(
            user_id=user_id,
            session_id=page_view.session_id,
            page_path=page_view.page_path,
            page_title=page_view.page_title,
            referrer=page_view.referrer,
            user_agent=user_agent,
            ip_address=ip_address,
            country_code=geolocation.get('country_code') if geolocation else None,
            country_name=geolocation.get('country_name') if geolocation else None,
            city=geolocation.get('city') if geolocation else None,
        )

        return {"success": True, "page_analytics_id": page_analytics_id}
    except Exception as e:
        logger.error(f"Failed to log page view: {e}")
        raise HTTPException(status_code=500, detail="Failed to log page view")


@router.put("/page-metrics")
async def update_page_metrics(metrics: PageMetricsUpdate):
    """Update page metrics (scroll depth, duration)."""
    try:
        PageAnalyticsRepository.update_page_metrics(
            page_analytics_id=metrics.page_analytics_id,
            visit_duration_seconds=metrics.visit_duration_seconds,
            max_scroll_depth_percent=metrics.max_scroll_depth_percent,
        )
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to update page metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to update page metrics")


@router.post("/click-event")
async def log_click_event(
    click_event: ClickEventRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional_dependency)
):
    """Log a click event."""
    try:
        # Get user ID if authenticated
        user_id = current_user.get("id") if current_user else None

        # Log to database
        click_event_id = PageAnalyticsRepository.log_click_event(
            page_analytics_id=click_event.page_analytics_id,
            user_id=user_id,
            session_id=click_event.session_id,
            page_path=click_event.page_path,
            element_type=click_event.element_type,
            element_id=click_event.element_id,
            element_text=click_event.element_text,
            element_class=click_event.element_class,
            click_position_x=click_event.click_position_x,
            click_position_y=click_event.click_position_y,
        )

        return {"success": True, "click_event_id": click_event_id}
    except Exception as e:
        logger.error(f"Failed to log click event: {e}")
        raise HTTPException(status_code=500, detail="Failed to log click event")


# Admin endpoints for viewing analytics
@router.get("/admin/stats")
async def get_page_analytics_stats(
    current_admin: dict = Depends(get_current_admin_user),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get aggregated page analytics statistics (admin only)."""
    try:
        stats = PageAnalyticsRepository.get_page_analytics_stats(
            start_date=start_date,
            end_date=end_date,
        )
        return stats
    except Exception as e:
        logger.error(f"Failed to get page analytics stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics stats")


@router.get("/admin/page-views")
async def get_page_views(
    current_admin: dict = Depends(get_current_admin_user),
    limit: int = 100,
    offset: int = 0,
    user_id: Optional[int] = None,
    page_path: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get page view records (admin only)."""
    try:
        page_views = PageAnalyticsRepository.get_page_views(
            limit=limit,
            offset=offset,
            user_id=user_id,
            page_path=page_path,
            start_date=start_date,
            end_date=end_date,
        )
        return {"page_views": page_views}
    except Exception as e:
        logger.error(f"Failed to get page views: {e}")
        raise HTTPException(status_code=500, detail="Failed to get page views")


@router.get("/admin/page-path-stats")
async def get_page_path_stats(
    current_admin: dict = Depends(get_current_admin_user),
    limit: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get statistics grouped by page path (admin only)."""
    try:
        stats = PageAnalyticsRepository.get_page_path_stats(
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )
        return {"page_stats": stats}
    except Exception as e:
        logger.error(f"Failed to get page path stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get page path stats")


@router.get("/admin/click-events")
async def get_click_events(
    current_admin: dict = Depends(get_current_admin_user),
    limit: int = 100,
    offset: int = 0,
    page_analytics_id: Optional[int] = None,
    user_id: Optional[int] = None,
    page_path: Optional[str] = None,
    element_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get click event records (admin only)."""
    try:
        clicks = PageAnalyticsRepository.get_click_events(
            limit=limit,
            offset=offset,
            page_analytics_id=page_analytics_id,
            user_id=user_id,
            page_path=page_path,
            element_type=element_type,
            start_date=start_date,
            end_date=end_date,
        )
        return {"clicks": clicks}
    except Exception as e:
        logger.error(f"Failed to get click events: {e}")
        raise HTTPException(status_code=500, detail="Failed to get click events")


@router.get("/admin/click-stats")
async def get_click_stats(
    current_admin: dict = Depends(get_current_admin_user),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get click statistics grouped by element type (admin only)."""
    try:
        stats = PageAnalyticsRepository.get_click_stats(
            start_date=start_date,
            end_date=end_date,
        )
        return {"click_stats": stats}
    except Exception as e:
        logger.error(f"Failed to get click stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get click stats")
