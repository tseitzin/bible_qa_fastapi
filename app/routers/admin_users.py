"""Admin endpoints for user management."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from pydantic import BaseModel

from app.auth import get_current_admin_user
from app.database import get_db_connection

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


class UserListItem(BaseModel):
    """User list item for admin view."""
    id: int
    email: str
    username: str
    is_active: bool
    is_admin: bool
    created_at: str
    question_count: int
    saved_answer_count: int


class UserDetail(BaseModel):
    """Detailed user information for admin."""
    id: int
    email: str
    username: str
    is_active: bool
    is_admin: bool
    created_at: str
    question_count: int
    saved_answer_count: int
    recent_question_count: int
    last_activity: Optional[str]


class UserStats(BaseModel):
    """User statistics."""
    total_users: int
    active_users: int
    admin_users: int
    users_with_questions: int


@router.get("/", response_model=List[UserListItem])
async def list_users(
    current_admin: dict = Depends(get_current_admin_user),
    search: Optional[str] = Query(None, description="Search by email or username"),
    active_only: bool = Query(False, description="Show only active users"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """List all users with basic stats."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query_parts = [
                    """
                    SELECT 
                        u.id,
                        u.email,
                        u.username,
                        u.is_active,
                        u.is_admin,
                        u.created_at,
                        COUNT(DISTINCT q.id) as question_count,
                        COUNT(DISTINCT sa.id) as saved_answer_count
                    FROM users u
                    LEFT JOIN questions q ON u.id = q.user_id
                    LEFT JOIN saved_answers sa ON u.id = sa.user_id
                    WHERE 1=1
                    """
                ]
                params = []
                
                if search:
                    query_parts.append("AND (u.email ILIKE %s OR u.username ILIKE %s)")
                    search_pattern = f"%{search}%"
                    params.extend([search_pattern, search_pattern])
                
                if active_only:
                    query_parts.append("AND u.is_active = true")
                
                query_parts.append("GROUP BY u.id, u.email, u.username, u.is_active, u.is_admin, u.created_at")
                query_parts.append("ORDER BY u.created_at DESC")
                query_parts.append("LIMIT %s OFFSET %s")
                params.extend([limit, offset])
                
                cur.execute(" ".join(query_parts), params)
                users = cur.fetchall()
                
                return [
                    UserListItem(
                        id=user["id"],
                        email=user["email"] or "",
                        username=user["username"] or "",
                        is_active=user["is_active"],
                        is_admin=user["is_admin"],
                        created_at=user["created_at"].isoformat() if user["created_at"] else "",
                        question_count=user["question_count"] or 0,
                        saved_answer_count=user["saved_answer_count"] or 0,
                    )
                    for user in users
                ]
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail="Failed to list users")


@router.get("/stats", response_model=UserStats)
async def get_user_stats(current_admin: dict = Depends(get_current_admin_user)):
    """Get overall user statistics."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_users,
                        COUNT(*) FILTER (WHERE is_active = true) as active_users,
                        COUNT(*) FILTER (WHERE is_admin = true) as admin_users
                    FROM users
                """)
                stats = cur.fetchone()
                
                # Get users with questions separately
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as users_with_questions
                    FROM questions
                """)
                question_stats = cur.fetchone()
                
                return UserStats(
                    total_users=stats["total_users"] or 0,
                    active_users=stats["active_users"] or 0,
                    admin_users=stats["admin_users"] or 0,
                    users_with_questions=question_stats["users_with_questions"] or 0,
                )
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user stats")


@router.get("/{user_id}", response_model=UserDetail)
async def get_user_detail(
    user_id: int,
    current_admin: dict = Depends(get_current_admin_user),
):
    """Get detailed information about a specific user."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        u.id,
                        u.email,
                        u.username,
                        u.is_active,
                        u.is_admin,
                        u.created_at,
                        COUNT(DISTINCT q.id) as question_count,
                        COUNT(DISTINCT sa.id) as saved_answer_count,
                        COUNT(DISTINCT rq.id) as recent_question_count,
                        MAX(q.asked_at) as last_activity
                    FROM users u
                    LEFT JOIN questions q ON u.id = q.user_id
                    LEFT JOIN saved_answers sa ON u.id = sa.user_id
                    LEFT JOIN recent_questions rq ON u.id = rq.user_id
                    WHERE u.id = %s
                    GROUP BY u.id, u.email, u.username, u.is_active, u.is_admin, u.created_at
                """, (user_id,))
                
                user = cur.fetchone()
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                return UserDetail(
                    id=user["id"],
                    email=user["email"] or "",
                    username=user["username"] or "",
                    is_active=user["is_active"],
                    is_admin=user["is_admin"],
                    created_at=user["created_at"].isoformat() if user["created_at"] else "",
                    question_count=user["question_count"] or 0,
                    saved_answer_count=user["saved_answer_count"] or 0,
                    recent_question_count=user["recent_question_count"] or 0,
                    last_activity=user["last_activity"].isoformat() if user["last_activity"] else None,
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user detail")


@router.post("/{user_id}/reset-account")
async def reset_user_account(
    user_id: int,
    current_admin: dict = Depends(get_current_admin_user),
):
    """Reset user account by clearing all questions, answers, and related data."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="User not found")
                
                # Delete all user data (cascading deletes will handle related records)
                # Questions table has ON DELETE CASCADE, so answers will be deleted too
                cur.execute("DELETE FROM questions WHERE user_id = %s", (user_id,))
                deleted_questions = cur.rowcount
                
                # Delete saved answers (already cascaded, but explicit for clarity)
                cur.execute("DELETE FROM saved_answers WHERE user_id = %s", (user_id,))
                deleted_saved = cur.rowcount
                
                # Delete recent questions
                cur.execute("DELETE FROM recent_questions WHERE user_id = %s", (user_id,))
                deleted_recent = cur.rowcount
                
                # Delete user notes
                cur.execute("DELETE FROM user_notes WHERE user_id = %s", (user_id,))
                deleted_notes = cur.rowcount
                
                # Delete user reading plan progress
                cur.execute("DELETE FROM user_reading_plan_days WHERE user_id IN (SELECT id FROM user_reading_plans WHERE user_id = %s)", (user_id,))
                cur.execute("DELETE FROM user_reading_plans WHERE user_id = %s", (user_id,))
                deleted_plans = cur.rowcount
                
                conn.commit()
                
                logger.info(f"Admin {current_admin['id']} reset account for user {user_id}")
                
                return {
                    "status": "success",
                    "message": "User account reset successfully",
                    "deleted": {
                        "questions": deleted_questions,
                        "saved_answers": deleted_saved,
                        "recent_questions": deleted_recent,
                        "notes": deleted_notes,
                        "reading_plans": deleted_plans,
                    }
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting user account: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset user account")


@router.post("/{user_id}/clear-saved-answers")
async def clear_saved_answers(
    user_id: int,
    current_admin: dict = Depends(get_current_admin_user),
):
    """Clear all saved answers for a user."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="User not found")
                
                cur.execute("DELETE FROM saved_answers WHERE user_id = %s", (user_id,))
                deleted_count = cur.rowcount
                conn.commit()
                
                logger.info(f"Admin {current_admin['id']} cleared {deleted_count} saved answers for user {user_id}")
                
                return {
                    "status": "success",
                    "message": f"Cleared {deleted_count} saved answer(s)",
                    "deleted_count": deleted_count,
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing saved answers: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear saved answers")


@router.post("/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    current_admin: dict = Depends(get_current_admin_user),
):
    """Toggle user active status."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get current status
                cur.execute("SELECT is_active FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                # Don't allow disabling the current admin
                if user_id == current_admin["id"]:
                    raise HTTPException(status_code=400, detail="Cannot disable your own account")
                
                new_status = not user["is_active"]
                cur.execute("UPDATE users SET is_active = %s WHERE id = %s", (new_status, user_id))
                conn.commit()
                
                action = "activated" if new_status else "deactivated"
                logger.info(f"Admin {current_admin['id']} {action} user {user_id}")
                
                return {
                    "status": "success",
                    "message": f"User {action} successfully",
                    "is_active": new_status,
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling user active status: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle user active status")


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: dict = Depends(get_current_admin_user),
):
    """Permanently delete a user and all their data."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()
                
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                # Don't allow deleting yourself
                if user_id == current_admin["id"]:
                    raise HTTPException(status_code=400, detail="Cannot delete your own account")
                
                # Delete user (cascade will handle all related data)
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()
                
                logger.warning(f"Admin {current_admin['id']} permanently deleted user {user_id} ({user['email']})")
                
                return {
                    "status": "success",
                    "message": "User permanently deleted",
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user")


@router.post("/cleanup-guest-users")
async def cleanup_guest_users(
    current_admin: dict = Depends(get_current_admin_user),
):
    """Clean up invalid guest user accounts (all users without email except user_id=1)."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Find guest users (no email, not user_id=1)
                cur.execute("""
                    SELECT id, username 
                    FROM users 
                    WHERE (email IS NULL OR email = '') 
                    AND id != 1
                    ORDER BY id
                """)
                guest_users = cur.fetchall()
                
                if not guest_users:
                    return {
                        "status": "success",
                        "message": "No guest users to clean up",
                        "deleted_count": 0,
                    }
                
                # Delete all guest users except user_id=1
                cur.execute("""
                    DELETE FROM users 
                    WHERE (email IS NULL OR email = '') 
                    AND id != 1
                """)
                deleted_count = cur.rowcount
                conn.commit()
                
                logger.info(f"Admin {current_admin['id']} cleaned up {deleted_count} guest users")
                
                return {
                    "status": "success",
                    "message": f"Cleaned up {deleted_count} guest user(s)",
                    "deleted_count": deleted_count,
                    "deleted_users": [f"user_{u['id']} (ID: {u['id']})" for u in guest_users],
                }
    except Exception as e:
        logger.error(f"Error cleaning up guest users: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup guest users")
