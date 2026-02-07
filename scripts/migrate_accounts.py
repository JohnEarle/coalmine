#!/usr/bin/env python3
"""
Coalmine Database Migration: Add account_id to legacy tables

This migration adds the account_id column to tables that were created
before the Account/Credential abstraction was introduced.

Safe to run multiple times (checks if column exists first).
"""
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from src.models import engine


def migrate_account_support():
    """Add account_id columns to legacy tables that predate the Account model."""
    print("Coalmine Database Migration: Account Support")
    print("=" * 50)
    
    with engine.connect() as conn:
        # Check if this is PostgreSQL
        is_postgres = str(engine.url).startswith('postgresql')
        if not is_postgres:
            print("SQLite detected - skipping (SQLite recreates tables automatically)")
            return
        
        # Tables that need account_id column
        migrations = [
            {
                'table': 'canary_resources',
                'column': 'account_id',
                'type': 'UUID',
                'fk': 'accounts(id)',
            },
            {
                'table': 'logging_resources',
                'column': 'account_id', 
                'type': 'UUID',
                'fk': 'accounts(id)',
            },
        ]
        
        for mig in migrations:
            table = mig['table']
            column = mig['column']
            col_type = mig['type']
            
            # Check if column already exists
            result = conn.execute(text("""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = :table AND column_name = :column
            """), {'table': table, 'column': column})
            
            if result.fetchone():
                print(f"✓ {table}.{column} already exists")
            else:
                print(f"  Adding {table}.{column}...")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                
                # Add foreign key if specified
                if mig.get('fk'):
                    fk_name = f"fk_{table}_{column}"
                    try:
                        conn.execute(text(f"""
                            ALTER TABLE {table} 
                            ADD CONSTRAINT {fk_name} 
                            FOREIGN KEY ({column}) REFERENCES {mig['fk']}
                        """))
                        print(f"  Added foreign key {fk_name}")
                    except Exception as e:
                        print(f"  Warning: Could not add FK (may already exist): {e}")
                
                print(f"✓ Added {table}.{column}")
        
        # Also add any missing columns to canary_resources
        missing_columns = [
            ('canary_resources', 'last_checked_at', 'TIMESTAMP'),
            ('canary_resources', 'canary_credentials', 'JSONB'),
        ]
        
        for table, column, col_type in missing_columns:
            result = conn.execute(text("""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = :table AND column_name = :column
            """), {'table': table, 'column': column})
            
            if result.fetchone():
                print(f"✓ {table}.{column} already exists")
            else:
                print(f"  Adding {table}.{column}...")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                print(f"✓ Added {table}.{column}")
        
        # Make legacy environment_id columns nullable (deprecated in favor of account_id)
        deprecated_columns = [
            ('logging_resources', 'environment_id'),
            ('canary_resources', 'environment_id'),
        ]
        
        for table, column in deprecated_columns:
            # Check if column exists and is NOT NULL
            result = conn.execute(text("""
                SELECT is_nullable FROM information_schema.columns 
                WHERE table_name = :table AND column_name = :column
            """), {'table': table, 'column': column})
            row = result.fetchone()
            
            if row and row[0] == 'NO':
                print(f"  Making {table}.{column} nullable (deprecated)...")
                try:
                    conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL"))
                    print(f"✓ Made {table}.{column} nullable")
                except Exception as e:
                    print(f"  Warning: Could not alter {column}: {e}")
            elif row:
                print(f"✓ {table}.{column} is already nullable")
            else:
                print(f"  {table}.{column} does not exist (OK)")
        
        conn.commit()
    
    print("\nMigration complete.")


def main():
    try:
        migrate_account_support()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
