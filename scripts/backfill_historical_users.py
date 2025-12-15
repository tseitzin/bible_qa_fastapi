#!/usr/bin/env python3
"""
Backfill user_id for historical API request logs.

This script analyzes historical API logs without user_id and creates
retroactive guest user accounts based on IP address and temporal patterns.
It groups requests by IP and time windows to identify unique visitors.
"""

import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_db_connection


def backfill_historical_users(dry_run=True):
    """
    Backfill user_id for historical API logs by creating guest users.
    
    Strategy:
    1. Find all logs without user_id
    2. Group by IP address and time windows (session timeout = 30 minutes)
    3. Create guest users for each unique session
    4. Update logs with the corresponding user_id
    
    Args:
        dry_run: If True, only show what would be done without making changes
    """
    
    print("=" * 70)
    print("Historical User Data Backfill Script")
    print("=" * 70)
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made to the database")
    else:
        print("⚠️  LIVE MODE - Changes will be committed to the database")
    print()
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get count of logs without user_id
            cur.execute("""
                SELECT COUNT(*) as count
                FROM api_request_logs
                WHERE user_id IS NULL
            """)
            untracked_count = cur.fetchone()['count']
            
            print(f"Found {untracked_count} API logs without user_id")
            print()
            
            if untracked_count == 0:
                print("✓ No logs need backfilling!")
                return
            
            # Get all untracked logs grouped by IP, ordered by time
            cur.execute("""
                SELECT id, ip_address, timestamp, endpoint, method
                FROM api_request_logs
                WHERE user_id IS NULL
                ORDER BY ip_address, timestamp
            """)
            logs = cur.fetchall()
            
            print(f"Processing {len(logs)} logs...")
            print()
            
            # Group logs into sessions
            # A session is defined as requests from the same IP within 30 minutes
            SESSION_TIMEOUT = timedelta(minutes=30)
            sessions = []
            current_session = None
            
            for log in logs:
                ip = log['ip_address'] or 'unknown'
                timestamp = log['timestamp']
                log_id = log['id']
                
                # Start a new session or continue existing one
                if (current_session is None or 
                    current_session['ip'] != ip or
                    (timestamp - current_session['last_timestamp']) > SESSION_TIMEOUT):
                    
                    # Save previous session if exists
                    if current_session:
                        sessions.append(current_session)
                    
                    # Start new session
                    current_session = {
                        'ip': ip,
                        'first_timestamp': timestamp,
                        'last_timestamp': timestamp,
                        'log_ids': [log_id],
                        'endpoints': [log['endpoint']],
                        'request_count': 1
                    }
                else:
                    # Continue current session
                    current_session['last_timestamp'] = timestamp
                    current_session['log_ids'].append(log_id)
                    current_session['endpoints'].append(log['endpoint'])
                    current_session['request_count'] += 1
            
            # Don't forget the last session
            if current_session:
                sessions.append(current_session)
            
            print(f"Identified {len(sessions)} unique visitor sessions")
            print()
            
            # Show session summary
            print("Session Summary:")
            print("-" * 70)
            for i, session in enumerate(sessions[:10], 1):
                duration = session['last_timestamp'] - session['first_timestamp']
                print(f"  {i}. IP: {session['ip'][:20]:<20} "
                      f"Requests: {session['request_count']:<4} "
                      f"Duration: {str(duration).split('.')[0]}")
            
            if len(sessions) > 10:
                print(f"  ... and {len(sessions) - 10} more sessions")
            print()
            
            # Statistics
            total_requests = sum(s['request_count'] for s in sessions)
            avg_requests = total_requests / len(sessions) if sessions else 0
            print(f"📊 Statistics:")
            print(f"   Total sessions: {len(sessions)}")
            print(f"   Total requests: {total_requests}")
            print(f"   Avg requests per session: {avg_requests:.1f}")
            print()
            
            if dry_run:
                print("✓ Dry run complete. Run with --live to apply changes.")
                return
            
            # Confirm before proceeding
            response = input("Proceed with backfilling? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return
            
            print()
            print("Creating guest users and updating logs...")
            
            # Create guest users and update logs
            created_users = 0
            updated_logs = 0
            
            for i, session in enumerate(sessions, 1):
                # Create a guest user for this session
                guest_username = f"guest_historical_{i:04d}"
                
                cur.execute("""
                    INSERT INTO users (username, email, is_active, is_admin, is_guest, last_ip_address, created_at)
                    VALUES (%s, NULL, TRUE, FALSE, TRUE, %s, %s)
                    RETURNING id
                """, (guest_username, session['ip'], session['first_timestamp']))
                
                user_id = cur.fetchone()['id']
                created_users += 1
                
                # Update all logs in this session with the new user_id
                for log_id in session['log_ids']:
                    cur.execute("""
                        UPDATE api_request_logs
                        SET user_id = %s
                        WHERE id = %s
                    """, (user_id, log_id))
                    updated_logs += 1
                
                if i % 10 == 0:
                    print(f"  Progress: {i}/{len(sessions)} sessions processed...")
            
            # Commit the changes
            conn.commit()
            
            print()
            print("=" * 70)
            print("✓ Backfill Complete!")
            print("=" * 70)
            print(f"Created {created_users} guest users")
            print(f"Updated {updated_logs} API log entries")
            print()
            print("The Admin Users tab should now show historical visitor data!")
            print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Backfill user_id for historical API logs"
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Actually perform the backfill (default is dry-run mode)'
    )
    
    args = parser.parse_args()
    
    try:
        backfill_historical_users(dry_run=not args.live)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
