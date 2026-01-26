import sys
import os
sys.path.append(os.getcwd()) # Ensure root is in path
import json
from src.models import SessionLocal, CloudEnvironment

def add_env(name, provider_type, access_key, secret_key):
    db = SessionLocal()
    try:
        # Check if exists
        existing = db.query(CloudEnvironment).filter(CloudEnvironment.name == name).first()
        if existing:
            print(f"Environment '{name}' already exists.")
            return

        creds = {}
        if provider_type.upper() == "AWS":
            creds = {
                "AWS_ACCESS_KEY_ID": access_key,
                "AWS_SECRET_ACCESS_KEY": secret_key
            }
        elif provider_type.upper() == "GCP":
            # For GCP usually we might want a path or content, but keeping it simple for now
            # Assume user might pass json key content or file path in access_key (not ideal but works for simple demo)
            pass

        # Config is now empty or generic, region is passed at item creation
        config = {}

        env = CloudEnvironment(
            name=name,
            provider_type=provider_type,
            credentials=creds,
            config=config
        )
        db.add(env)
        db.commit()
        db.refresh(env)
        print(f"Environment '{name}' created successfully.")
        print(f"ID: {env.id}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

def list_envs():
    db = SessionLocal()
    try:
        envs = db.query(CloudEnvironment).all()
        print(f"{'ID':<38} | {'Name':<20} | {'Provider':<10} | {'Region'}")
        print("-" * 80)
        for env in envs:
            region = env.config.get('region', 'N/A') if env.config else 'N/A'
            print(f"{str(env.id):<38} | {env.name:<20} | {env.provider_type:<10} | {region}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  List: python src/manage_env.py list")
        print("  Add AWS: python src/manage_env.py add_aws <name> <access_key> <secret_key> <region>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "list":
        list_envs()
    elif cmd == "add_aws":
        if len(sys.argv) < 5:
            print("Usage: python src/manage_env.py add_aws <name> <access_key> <secret_key>")
            sys.exit(1)
        add_env(sys.argv[2], "AWS", sys.argv[3], sys.argv[4])
