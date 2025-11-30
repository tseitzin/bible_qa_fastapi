"""Admin API endpoints for viewing API request logs."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import get_current_admin_user
from app.database import ApiRequestLogRepository, OpenAIApiCallRepository


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
        # Convert psycopg2 RealDictRow to regular dict
        if stats:
            result = dict(stats)
            # Ensure all values are integers
            return {
                "total_requests": int(result.get("total_requests", 0)),
                "unique_users": int(result.get("unique_users", 0)),
                "successful_requests": int(result.get("successful_requests", 0)),
                "error_requests": int(result.get("error_requests", 0)),
                "openai_requests": int(result.get("openai_requests", 0))
            }
        else:
            return {
                "total_requests": 0,
                "unique_users": 0,
                "successful_requests": 0,
                "error_requests": 0,
                "openai_requests": 0
            }
    except Exception as e:
        import traceback
        print(f"Error in get_api_stats: {str(e)}")
        print(traceback.format_exc())
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


@router.get("/openai", dependencies=[Depends(get_current_admin_user)])
async def get_openai_calls(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of calls to return"),
    offset: int = Query(0, ge=0, description="Number of calls to skip"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    status: Optional[str] = Query(None, description="Filter by status (success, error, rate_limit)"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
):
    """Get OpenAI API call logs with optional filters (admin only)."""
    try:
        calls = OpenAIApiCallRepository.get_calls(
            limit=limit,
            offset=offset,
            user_id=user_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "calls": calls,
            "count": len(calls),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch OpenAI calls: {str(e)}")


@router.get("/openai/stats", dependencies=[Depends(get_current_admin_user)])
async def get_openai_stats(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
):
    """Get aggregated OpenAI usage statistics (admin only)."""
    try:
        stats = OpenAIApiCallRepository.get_usage_stats(
            start_date=start_date,
            end_date=end_date,
        )
        # Convert to dict and ensure all values are properly typed
        if stats:
            result = dict(stats)
            return {
                "total_calls": int(result.get("total_calls", 0) or 0),
                "unique_users": int(result.get("unique_users", 0) or 0),
                "total_tokens_used": int(result.get("total_tokens_used", 0) or 0),
                "total_prompt_tokens": int(result.get("total_prompt_tokens", 0) or 0),
                "total_completion_tokens": int(result.get("total_completion_tokens", 0) or 0),
                "avg_tokens_per_call": float(result.get("avg_tokens_per_call", 0) or 0),
                "avg_response_time_ms": float(result.get("avg_response_time_ms", 0) or 0),
                "successful_calls": int(result.get("successful_calls", 0) or 0),
                "error_calls": int(result.get("error_calls", 0) or 0),
                "rate_limit_calls": int(result.get("rate_limit_calls", 0) or 0)
            }
        else:
            return {
                "total_calls": 0,
                "unique_users": 0,
                "total_tokens_used": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "avg_tokens_per_call": 0,
                "avg_response_time_ms": 0,
                "successful_calls": 0,
                "error_calls": 0,
                "rate_limit_calls": 0
            }
    except Exception as e:
        import traceback
        print(f"Error in get_openai_stats: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch OpenAI stats: {str(e)}")


@router.get("/openai/users", dependencies=[Depends(get_current_admin_user)])
async def get_openai_user_usage(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of users to return"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
):
    """Get OpenAI usage statistics grouped by user (admin only)."""
    try:
        users = OpenAIApiCallRepository.get_user_usage(
            limit=limit,
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "users": users,
            "count": len(users),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch user usage: {str(e)}")
