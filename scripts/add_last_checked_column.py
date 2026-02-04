import sys
import os
# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from src.models import engine

def migrate():
    print("Migrating: Adding last_checked_at to canary_resources...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE canary_resources ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMP"))
            conn.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
