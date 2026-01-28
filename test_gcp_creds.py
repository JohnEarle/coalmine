
import os
import json
from src.tasks.helpers import _build_env_vars, _write_gcp_creds
from src.models import CloudEnvironment

# Mock Environment with YAML-style config
creds_content = {
    "type": "service_account",
    "project_id": "extracted-project-id",
    "private_key_id": "..."
}

# Test 1: Current YAML style (service_account_json key)
env_yaml_style = CloudEnvironment(
    name="test",
    provider_type="GCP",
    credentials={"service_account_json": json.dumps(creds_content)},
    config={}
)

# Test 2: Supported style (GOOGLE_CREDENTIALS_JSON)
env_supported = CloudEnvironment(
    name="test2",
    provider_type="GCP",
    credentials={"GOOGLE_CREDENTIALS_JSON": json.dumps(creds_content)},
    config={}
)

print("--- Test 1: YAML Style (service_account_json) ---")
env_vars_1 = _build_env_vars(env_yaml_style)
print(f"GOOGLE_APPLICATION_CREDENTIALS: {env_vars_1.get('GOOGLE_APPLICATION_CREDENTIALS')}")
print(f"GOOGLE_CLOUD_PROJECT: {env_vars_1.get('GOOGLE_CLOUD_PROJECT')}")

print("\n--- Test 2: Supported Style (GOOGLE_CREDENTIALS_JSON) ---")
env_vars_2 = _build_env_vars(env_supported)
print(f"GOOGLE_APPLICATION_CREDENTIALS: {env_vars_2.get('GOOGLE_APPLICATION_CREDENTIALS')}")
print(f"GOOGLE_CLOUD_PROJECT: {env_vars_2.get('GOOGLE_CLOUD_PROJECT')}")
