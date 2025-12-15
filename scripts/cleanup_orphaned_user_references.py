"""
Cleanup script to remove orphaned user_id references from api_request_logs.

This script sets user_id to NULL for any api_request_logs entries that reference
users that no longer exist in the users table.
"""

import sys
from pathlib import Path

# Add parent directory to path to import from app
sys.path.append(str(Path(__file__).parent.parent))

from app.database import get_db_connection


def cleanup_orphaned_references():
    """Remove orphaned user_id references from api_request_logs."""
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # First, check how many orphaned references exist
            cur.execute("""
                SELECT COUNT(*) 
                FROM api_request_logs 
                WHERE user_id IS NOT NULL 
                AND user_id NOT IN (SELECT id FROM users)
            """)
            orphaned_count = cur.fetchone()['count']
            
            print(f"Found {orphaned_count} orphaned user references in api_request_logs")
            
            if orphaned_count == 0:
                print("No cleanup needed!")
                return
            
            # Update orphaned references to NULL
            cur.execute("""
                UPDATE api_request_logs 
                SET user_id = NULL 
                WHERE user_id IS NOT NULL 
                AND user_id NOT IN (SELECT id FROM users)
            """)
            
            conn.commit()
            
            print(f"✓ Cleaned up {orphaned_count} orphaned user references")
            
            # Verify the cleanup
            cur.execute("""
                SELECT COUNT(DISTINCT user_id) 
                FROM api_request_logs 
                WHERE user_id IS NOT NULL
            """)
            unique_users = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()['count']
            
            print(f"\nVerification:")
            print(f"  Users in users table: {total_users}")
            print(f"  Unique user_ids in api_request_logs: {unique_users}")
            print(f"  Match: {'✓' if unique_users <= total_users else '✗'}")


if __name__ == "__main__":
    print("Starting cleanup of orphaned user references...\n")
    cleanup_orphaned_references()
    print("\nCleanup complete!")
