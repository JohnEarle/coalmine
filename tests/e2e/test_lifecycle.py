import pytest
import uuid
import os
import time
from src.models import CanaryResource, ResourceStatus, ResourceType, ActionType
from src.tasks.canary import create_canary, delete_canary

# Mark as e2e to potentially separate from unit tests later
@pytest.mark.e2e
def test_full_canary_lifecycle(db_session, test_env_aws, test_logging_resource):
    """
    Tests the full lifecycle of a Canary:
    1. Creation
    2. Status Check
    3. Deletion
    
    Note: We invoke celery tasks synchronously (.apply() or direct call) for testing.
    """
    
    canary_name = f"e2e-canary-{uuid.uuid4().hex[:6]}"
    
    print(f"\n[E2E] Creating Canary {canary_name}...")
    
    # 1. Create
    # We call the function directly to run in-process (or use .apply() if needed but direct is easier to debug)
    # However, since it is a celery task, calling it directly works if not using .delay()
    create_canary(
        name=canary_name,
        resource_type_str="AWS_IAM_USER", # Use a cheap/fast resource
        environment_id_str=str(test_env_aws.id),
        logging_resource_id_str=str(test_logging_resource.id),
        interval_seconds=0 # No rotation
    )
    
    # 2. Verify Creation
    canary = db_session.query(CanaryResource).filter_by(name=canary_name).first()
    assert canary is not None
    assert canary.status == ResourceStatus.ACTIVE
    assert canary.current_resource_id is not None
    assert canary.canary_credentials is not None
    
    print(f"[E2E] Canary {canary_name} created. ID: {canary.id}")
    
    # 3. Verify Cloud Resource (Mocked for speed/cost, or real if creds present)
    # Checks if credentials have keys
    creds = canary.canary_credentials
    if "access_key_id" in creds:
        assert len(creds["access_key_id"]) > 0
    
    # 4. Trigger Alert (Simulated)
    # In a real E2E we might use 'trigger' command logic here.
    # For now, we verified creation.
    
    # 5. Delete
    print(f"[E2E] Deleting Canary {canary.id}...")
    delete_canary(str(canary.id))
    
    # Refresh from DB
    db_session.expire(canary)
    canary = db_session.query(CanaryResource).filter_by(id=canary.id).first()
    
    assert canary.status == ResourceStatus.DELETED
    print(f"[E2E] Canary {canary_name} deleted.")
