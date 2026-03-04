#!/usr/bin/env python3
"""
Manual database migration runner.

This script forces a database migration by instantiating the DatabaseManager,
which automatically runs all pending migrations defined in add_missing_columns().

Usage:
    python run_migrations.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from db.database_manager import DatabaseManager
from config.logger_manager import LoggerManager

logger = LoggerManager.get_logger("MigrationRunner")


def main():
    """Run database migrations."""
    print("=" * 60)
    print("SuggestArr Database Migration Runner")
    print("=" * 60)
    print()
    
    try:
        logger.info("Initializing DatabaseManager to trigger migrations...")
        db = DatabaseManager()
        
        print("✓ Database migrations completed successfully!")
        print()
        print("Verifying auth_users table structure...")
        
        # Verify the new columns exist
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            if db.db_type == 'sqlite':
                cursor.execute("PRAGMA table_info(auth_users);")
                columns = {row[1] for row in cursor.fetchall()}
            elif db.db_type == 'postgres':
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'auth_users';
                """)
                columns = {row[0] for row in cursor.fetchall()}
            elif db.db_type in ['mysql', 'mariadb']:
                cursor.execute("SHOW COLUMNS FROM auth_users;")
                columns = {row[0] for row in cursor.fetchall()}
            else:
                columns = set()
        
        print(f"  - can_manage_ai: {'✓ Present' if 'can_manage_ai' in columns else '✗ Missing'}")
        print(f"  - visible_tabs: {'✓ Present' if 'visible_tabs' in columns else '✗ Missing'}")
        print()
        
        print("Verifying discover_jobs table structure...")
        
        # Verify owner_id column exists
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            if db.db_type == 'sqlite':
                cursor.execute("PRAGMA table_info(discover_jobs);")
                columns = {row[1] for row in cursor.fetchall()}
            elif db.db_type == 'postgres':
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'discover_jobs';
                """)
                columns = {row[0] for row in cursor.fetchall()}
            elif db.db_type in ['mysql', 'mariadb']:
                cursor.execute("SHOW COLUMNS FROM discover_jobs;")
                columns = {row[0] for row in cursor.fetchall()}
            else:
                columns = set()
        
        print(f"  - owner_id: {'✓ Present' if 'owner_id' in columns else '✗ Missing'}")
        print()
        
        print("=" * 60)
        print("Migration verification complete!")
        print("You can now restart your Flask application.")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        print(f"✗ Migration failed: {e}")
        print()
        print("Please check the logs and fix any errors before retrying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
