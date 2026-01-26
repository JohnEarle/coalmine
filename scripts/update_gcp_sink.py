from src.models import SessionLocal, CanaryResource, ResourceType
from src.logging_utils import _update_gcp_sink_filter
from src.logging_config import get_logger

logger = get_logger(__name__)

db = SessionLocal()
try:
    canary = db.query(CanaryResource).filter(CanaryResource.name == "argus-canary-01").first()
    if canary and canary.logging_resource:
        logger.info(f"Updating sink for {canary.name}...")
        # We add it again. The logic handles 'OR fragment'. 
        # Since the fragment changed, it will validly append the NEW fragment.
        # The OLD fragment (partial) will remain, making the filter slightly redundant but valid.
        # (A OR B) OR A is valid.
        
        sink_name = canary.logging_resource.configuration.get("sink_name") or canary.logging_resource.name
        _update_gcp_sink_filter(
            canary.environment, 
            sink_name,
            canary.current_resource_id,
            canary.resource_type,
            add=True
        )
        logger.info("Sink update initiated.")
finally:
    db.close()
