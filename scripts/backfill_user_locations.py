#!/usr/bin/env python3
"""
Backfill user geolocation data from API request logs.

This script updates the users table with geolocation data from their
most recent API request log entry that has location information.
"""

import os
import sys

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_db_connection


def backfill_user_locations(dry_run=True):
    """
    Backfill user geolocation data from API request logs.
    
    Strategy:
    1. Find users without location data
    2. Look up their most recent API request log with location data
    3. Copy that location data to the user record
    
    Args:
        dry_run: If True, only show what would be done without making changes
    """
    
    print("=" * 70)
    print("User Location Backfill Script")
    print("=" * 70)
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made to the database")
    else:
        print("⚠️  LIVE MODE - Changes will be committed to the database")
    print()
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get count of users without location data
            cur.execute("""
                SELECT COUNT(*) as count
                FROM users
                WHERE country_code IS NULL
            """)
            users_without_location = cur.fetchone()['count']
            
            print(f"Found {users_without_location} users without location data")
            print()
            
            if users_without_location == 0:
                print("✓ No users need location backfilling!")
                return
            
            # Find users and their most recent location from API logs
            cur.execute("""
                SELECT DISTINCT ON (u.id)
                    u.id as user_id,
                    u.username,
                    u.last_ip_address,
                    l.country_code,
                    l.country_name,
                    l.city,
                    l.timestamp
                FROM users u
                INNER JOIN api_request_logs l ON u.id = l.user_id
                WHERE u.country_code IS NULL
                  AND l.country_code IS NOT NULL
                ORDER BY u.id, l.timestamp DESC
            """)
            user_locations = cur.fetchall()
            
            print(f"Found location data for {len(user_locations)} users from API logs")
            print()
            
            if len(user_locations) == 0:
                print("⚠️  No location data available in API logs to backfill")
                print("   Users need to make new requests to capture their location")
                return
            
            # Show sample
            print("Sample locations to be updated:")
            print("-" * 70)
            for i, ul in enumerate(user_locations[:10], 1):
                country = ul['country_code'] or 'N/A'
                city = ul['city'] or 'N/A'
                print(f"  {i}. User {ul['user_id']} ({ul['username'][:20]:<20}): "
                      f"{city}, {country}")
            
            if len(user_locations) > 10:
                print(f"  ... and {len(user_locations) - 10} more users")
            print()
            
            # Statistics
            countries = {}
            for ul in user_locations:
                country = ul['country_name'] or 'Unknown'
                countries[country] = countries.get(country, 0) + 1
            
            print(f"📊 Location Distribution:")
            for country, count in sorted(countries.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   {country}: {count} user(s)")
            print()
            
            if dry_run:
                print("✓ Dry run complete. Run with --live to apply changes.")
                return
            
            # Confirm before proceeding
            response = input("Proceed with updating user locations? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return
            
            print()
            print("Updating user locations...")
            
            # Update each user
            updated_count = 0
            for ul in user_locations:
                cur.execute("""
                    UPDATE users
                    SET country_code = %s,
                        country_name = %s,
                        city = %s,
                        region = NULL
                    WHERE id = %s
                """, (ul['country_code'], ul['country_name'], ul['city'], ul['user_id']))
                updated_count += 1
                
                if updated_count % 50 == 0:
                    print(f"  Progress: {updated_count}/{len(user_locations)} users updated...")
            
            # Commit the changes
            conn.commit()
            
            print()
            print("=" * 70)
            print("✓ Backfill Complete!")
            print("=" * 70)
            print(f"Updated {updated_count} user(s) with location data")
            print()
            print("The Admin Users tab should now show visitor locations!")
            print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Backfill user geolocation data from API logs"
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Actually perform the backfill (default is dry-run mode)'
    )
    
    args = parser.parse_args()
    
    try:
        backfill_user_locations(dry_run=not args.live)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
