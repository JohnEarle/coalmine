from src.models import SessionLocal, CanaryResource, ResourceType
from src.monitors.factory import get_monitor
from src.monitors.gcp_audit import GcpAuditMonitor
from src.config_loader import get_detection_config
import datetime
from src.monitors.strategies import GcpAuditLogQuery

db = SessionLocal()
try:
    canary = db.query(CanaryResource).filter(CanaryResource.name == "argus-canary-01").first()
    if not canary:
        print("Canary not found")
        exit(1)
        
    print(f"Testing monitor for {canary.name}...")
    
    # Manually setup strategy to match registry
    conf = get_detection_config("GCP_SERVICE_ACCOUNT")
    print(f"Config: {conf}")
    strategy = GcpAuditLogQuery(filter_template=conf["filter_template"])
    
    # Get Client
    monitor = GcpAuditMonitor(canary.environment) # Helper to get client
    client = monitor._get_client()
    
    end_time = datetime.datetime.utcnow()
    start_time = end_time - datetime.timedelta(minutes=60)
    
    print(f"Window: {start_time} to {end_time}")
    
    # We will print the generated filter
    phys_name = canary.current_resource_id
    filter_str = strategy.filter_template.format(
            resource_id=phys_name,
            start_time=start_time.isoformat() + "Z",
            end_time=end_time.isoformat() + "Z"
    )
    print(f"Filter: {filter_str}")
    
    alerts = strategy.detect(client, canary, start_time, end_time)
    print(f"Found {len(alerts)} alerts.")
    for a in alerts:
        print(f" - {a.event_time} {a.event_name}")

except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
