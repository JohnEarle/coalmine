import sys
import os
from sqlalchemy import text, create_engine

sys.path.append(os.getcwd())
# Check ENV
db_url = os.getenv("DATABASE_URL", "postgresql://canary_user:canary_password@postgres:5432/canary_inventory")

def migrate_enum():
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        try:
            print("Attempting to add value to enum...")
            # Postgres allows ALTER TYPE ... ADD VALUE
            # We catch error if it already exists
            conn.execute(text("ALTER TYPE loggingprovidertype ADD VALUE IF NOT EXISTS 'GCP_AUDIT_SINK'"))
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed (might be already done or sqlite?): {e}")

if __name__ == "__main__":
    migrate_enum()
