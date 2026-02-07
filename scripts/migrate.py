#!/usr/bin/env python3
"""
Coalmine Database Migration Script

Creates or updates the database schema. Safe to run multiple times.

Usage:
    python scripts/migrate.py [--force]

Options:
    --force    Drop and recreate all tables (WARNING: destroys data)
"""
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text, inspect
from src.models import Base, engine, SessionLocal
from src.models import (
    ResourceStatus, ResourceType, ActionType, AlertStatus, LoggingProviderType
)


def get_enum_values(enum_class):
    """Get all values from a Python enum."""
    return [e.value for e in enum_class]


def sync_enum_type(connection, enum_name: str, python_enum):
    """
    Synchronize PostgreSQL enum type with Python enum.
    Adds any missing values to the PostgreSQL enum.
    """
    # Get existing values from PostgreSQL
    result = connection.execute(text(f"""
        SELECT unnest(enum_range(NULL::{enum_name}))::text as value
    """))
    existing_values = {row[0] for row in result}
    
    # Get expected values from Python enum
    expected_values = set(get_enum_values(python_enum))
    
    # Add missing values
    missing = expected_values - existing_values
    for value in missing:
        print(f"  Adding '{value}' to {enum_name}")
        connection.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))
    
    if not missing:
        print(f"  {enum_name}: up to date")


def migrate(force: bool = False):
    """Run database migrations."""
    print("Coalmine Database Migration")
    print("=" * 40)
    
    # Check if we're using SQLite (for local development)
    is_sqlite = str(engine.url).startswith('sqlite')
    
    if is_sqlite:
        print("Using SQLite database (development mode)")
        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("Done.")
        return
    
    # PostgreSQL migrations
    print(f"Database: {engine.url.host}/{engine.url.database}")
    
    if force:
        print("\n⚠️  FORCE MODE: Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("Done.")
        return
    
    # Check if tables exist
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    if not existing_tables:
        print("\nNo existing tables. Creating schema...")
        Base.metadata.create_all(bind=engine)
        print("Schema created successfully.")
        return
    
    print(f"\nExisting tables: {', '.join(existing_tables)}")
    
    # Sync enum types
    print("\nSynchronizing enum types...")
    with engine.connect() as conn:
        # The enum types are named based on the Python class names (lowercase)
        enum_mappings = [
            ('resourcestatus', ResourceStatus),
            ('resourcetype', ResourceType),
            ('actiontype', ActionType),
            ('alertstatus', AlertStatus),
            ('loggingprovidertype', LoggingProviderType),
        ]
        
        for enum_name, python_enum in enum_mappings:
            try:
                sync_enum_type(conn, enum_name, python_enum)
            except Exception as e:
                print(f"  {enum_name}: {e}")
        
        conn.commit()
    
    # Create any missing tables
    print("\nEnsuring all tables exist...")
    Base.metadata.create_all(bind=engine)
    
    # Add any missing columns to legacy tables
    print("\nApplying column migrations...")
    try:
        from migrate_accounts import migrate_account_support
        migrate_account_support()
    except ImportError:
        # migrate_accounts.py might not exist in older versions
        pass
    except Exception as e:
        print(f"  Warning: account migration failed: {e}")
    
    print("\nMigration complete.")


def main():
    force = '--force' in sys.argv
    
    if force:
        confirm = input("This will DELETE ALL DATA. Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            sys.exit(1)
    
    try:
        migrate(force=force)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
