"""Admin API endpoints for viewing API request logs."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import get_current_admin_user
from app.database import ApiRequestLogRepository


router = APIRouter(prefix="/api/admin/logs", tags=["admin"])


class ApiLogStats(BaseModel):
    """API usage statistics."""
    total_requests: int
    unique_users: int
    successful_requests: int
    error_requests: int
    openai_requests: int


class EndpointStats(BaseModel):
    """Statistics for a single endpoint."""
    endpoint: str
    request_count: int
    success_rate: float


@router.get("/", dependencies=[Depends(get_current_admin_user)])
async def get_api_logs(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint (partial match)"),
    status_code: Optional[int] = Query(None, description="Filter by status code"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
):
    """Get API request logs with optional filters (admin only)."""
    try:
        logs = ApiRequestLogRepository.get_logs(
            limit=limit,
            offset=offset,
            user_id=user_id,
            endpoint=endpoint,
            status_code=status_code,
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "logs": logs,
            "count": len(logs),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {str(e)}")


@router.get("/stats", response_model=ApiLogStats, dependencies=[Depends(get_current_admin_user)])
async def get_api_stats(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
):
    """Get aggregated API usage statistics (admin only)."""
    try:
        stats = ApiRequestLogRepository.get_stats(
            start_date=start_date,
            end_date=end_date,
        )
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@router.get("/endpoints", dependencies=[Depends(get_current_admin_user)])
async def get_endpoint_stats(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of endpoints to return"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
):
    """Get statistics grouped by endpoint (admin only)."""
    try:
        stats = ApiRequestLogRepository.get_endpoint_stats(
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "endpoints": stats,
            "count": len(stats),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch endpoint stats: {str(e)}")
