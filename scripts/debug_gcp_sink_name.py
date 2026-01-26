from src.models import SessionLocal, LoggingResource
db = SessionLocal()
try:
    log_res = db.query(LoggingResource).filter(LoggingResource.name == "canary-audit-sink").first()
    if log_res:
        print(f"Name: {log_res.name}")
        print(f"Config: {log_res.configuration}")
finally:
    db.close()
