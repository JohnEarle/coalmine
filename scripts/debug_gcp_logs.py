import sys
import os
import datetime
sys.path.append(os.getcwd())
from src.models import SessionLocal, CanaryResource
from src.monitors.gcp_audit import GcpAuditMonitor

def debug_logs(canary_name):
    db = SessionLocal()
    try:
        canary = db.query(CanaryResource).filter(CanaryResource.name == canary_name).first()
        monitor = GcpAuditMonitor(canary.environment)
        client = monitor._get_client()
        
        print("Listing last 10 log entries (any kind)...")
        # List any logs from the last hour
        try:
             # List most recent first
             # List all logs from last 15 mins
             end_time = datetime.datetime.now(datetime.timezone.utc)
             start_time = end_time - datetime.timedelta(minutes=15)
             filter_str = f'timestamp >= "{start_time.isoformat()}"'
             entries = list(client.list_entries(filter_=filter_str, max_results=20, order_by="timestamp desc"))
             print(f"Total entries found: {len(entries)}")
             for e in entries:
                 print(f"[{e.timestamp}] {e.insert_id} {e.log_name}: {e.payload.get('methodName')}")
        except Exception as e:
            print(f"Error listing entries: {e}")
            
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_gcp_logs.py <canary_name>")
        sys.exit(1)
    debug_logs(sys.argv[1])
