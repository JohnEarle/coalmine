import sys
import os
sys.path.append(os.getcwd())

from src.tasks.monitoring import monitor_active_canaries
from src.models import SessionLocal, Alert, AlertStatus

if __name__ == "__main__":
    print("Running monitor task...")
    monitor_active_canaries()
    print("Done monitoring.")

    db = SessionLocal()
    alerts = db.query(Alert).all()
    print(f"\nTotal Alerts in DB: {len(alerts)}")
    for a in alerts:
        print(f"[{a.status.value}] {a.event_name} - {a.source_ip} (ID: {a.external_id})")
    
    db.close()
