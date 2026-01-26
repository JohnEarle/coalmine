
import sys
import os
import argparse
sys.path.append(os.getcwd()) # Ensure root is in path
import json
import boto3
from src.tasks import create_canary, create_logging_resource, delete_canary
from src.models import SessionLocal, CloudEnvironment, LoggingResource, ResourceType, CanaryResource, Alert
import uuid
from src.triggers import get_trigger

def scan_trails(env_id):
    """List available CloudTrails and LogGroups for the environment."""
    db = SessionLocal()
    try:
        env_obj = db.query(CloudEnvironment).filter(CloudEnvironment.id == uuid.UUID(env_id)).first()
        if not env_obj:
            print(f"Error: Environment {env_id} not found.")
            return

        creds = env_obj.credentials
        region = env_obj.config.get("region", "us-east-1")
        
        if env_obj.provider_type == "AWS":
            session = boto3.Session(
                aws_access_key_id=creds.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=creds.get("AWS_SECRET_ACCESS_KEY"),
                region_name=region
            )

            print(f"--- CloudTrails in {region} ---")
            ct = session.client("cloudtrail")
            try:
                trails = ct.describe_trails().get("trailList", [])
                for t in trails:
                    lg_arn = t.get("CloudWatchLogsLogGroupArn", "N/A")
                    print(f"- Name: {t['Name']}")
                    print(f"  ARN: {t['TrailARN']}")
                    print(f"  Log Group: {lg_arn}")
                    print("")
            except Exception as e:
                print(f"Error scanning trails: {e}")

            print(f"--- CloudWatch Log Groups in {region} ---")
            logs = session.client("logs")
            try:
                # Paginate? Just minimal list for now
                response = logs.describe_log_groups(limit=50)
                for lg in response.get("logGroups", []):
                     print(f"- Name: {lg['logGroupName']}")
                     print(f"  ARN: {lg['arn']}")
            except Exception as e:
                print(f"Error scanning logs: {e}")
                
        else:
            print("Only AWS supported for scan_trails currently.")

    finally:
        db.close()

def print_custom_help():
    help_text = """
Coalmine CLI - Usage Guide
================================

Canary Management:
  create <name> <type> --env <id> --logging-id <id> [--interval <sec>] [--params <json>]
      Create a new canary resource.
      Types: AWS_IAM_USER, AWS_BUCKET, GCP_SERVICE_ACCOUNT, GCP_BUCKET
  
  delete <name_or_id>
      Delete an existing canary.
  
  list
      List all active and recent canaries.
  
  get-creds <name>
      Retrieve credentials for a specific canary (e.g. Access Keys).

Alerting & Verification:
  list-alerts [--canary <name>] [--env <name>]
      View security alerts detected by the system.
  
  trigger <name_or_id>
      Manually trigger a test alert for a canary to verify detection.

Environment & Logging:
  create-env <name> <provider> --credentials <json> [--config <json>]
      Register a new cloud environment (AWS/GCP).
  
  list-envs
      List registered environments.
  
  create-log <name> <type> --env <id> [--config <json>]
      Configure a logging resource (e.g. CloudTrail, GCP Audit Sink).
  
  list-logs
      List configured logging resources.
  
  scan_trails --env <id>
      Scan an AWS account for existing CloudTrails and Log Groups.

General:
  help
      Show this help message.
"""
    print(help_text)

def run():
    parser = argparse.ArgumentParser(description="Coalmine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Create Canary
    parser_create = subparsers.add_parser("create", help="Create a canary")
    parser_create.add_argument("name", help="Logical name of the canary")
    parser_create.add_argument("type", help="Type of resource")
    parser_create.add_argument("--interval", type=int, default=0, help="Rotation interval in seconds (0 for static/no rotation)")
    parser_create.add_argument("--env", help="Environment ID (UUID)", required=True)
    parser_create.add_argument("--logging-id", help="Logging Resource ID (UUID)", required=True)
    parser_create.add_argument("--params", help="JSON string for module parameters", required=False)

    # Subparser for creating logging resources
    parser_create_log = subparsers.add_parser("create-log", help="Create a logging resource (e.g. CloudTrail)")
    parser_create_log.add_argument("name", help="Name of the logging resource")
    parser_create_log.add_argument("type", help="Type: AWS_CLOUDTRAIL, GCP_AUDIT_SINK")
    parser_create_log.add_argument("--env", help="Environment ID (UUID)", required=True)
    parser_create_log.add_argument("--config", help="JSON string for configuration", required=False)

    # Subparser for listing logging resources
    parser_list_logs = subparsers.add_parser("list-logs", help="List logging resources")

    # Subparser for creating cloud environments
    parser_create_env = subparsers.add_parser("create-env", help="Create a cloud environment")
    parser_create_env.add_argument("name", help="Name of the environment")
    parser_create_env.add_argument("provider", help="Provider type (e.g. AWS, GCP)")
    parser_create_env.add_argument("--credentials", help="JSON string for credentials", required=True)
    parser_create_env.add_argument("--config", help="JSON string for configuration", default="{}")

    # Command: scan_trails (Existing)
    parser_scan = subparsers.add_parser("scan_trails", help="Scan existing CloudTrails/LogGroups")
    parser_scan.add_argument("--env", help="Environment ID (UUID)", required=True)

    # Command: get-creds
    parser_creds = subparsers.add_parser("get-creds", help="Get credentials for a canary")
    parser_creds.add_argument("name", help="Name of the canary")

    # Command: list
    subparsers.add_parser("list", help="List all canaries")

    # Command: delete
    parser_delete = subparsers.add_parser("delete", help="Delete a canary")
    parser_delete.add_argument("name_or_id", help="Name or ID of the canary to delete")

    # Command: trigger
    parser_trigger = subparsers.add_parser("trigger", help="Trigger a test alert for a canary")
    parser_trigger.add_argument("name_or_id", help="Name or ID of the canary")

    # Command: list-alerts
    parser_alerts = subparsers.add_parser("list-alerts", help="List alerts")
    parser_alerts.add_argument("--canary", help="Filter by Canary Name or ID", required=False)
    parser_alerts.add_argument("--env", help="Filter by Environment Name or ID", required=False)

    # Command: list-envs
    subparsers.add_parser("list-envs", help="List cloud environments")

    # Command: help
    subparsers.add_parser("help", help="Show detailed usage guide")

    # Legacy support check
    if len(sys.argv) > 1 and sys.argv[1] not in ["create", "create-log", "list-logs", "create-env", "scan_trails", "get-creds", "list", "delete", "list-envs", "list-alerts", "trigger", "help", "-h", "--help"]:
         print("Using legacy flow is deprecated. Please use 'create' subcommand.")
         # Fallback logic removed for clarity, user should switch.
         return

    args = parser.parse_args()

    if args.command == "create":
        params = None
        if args.params:
            try:
                params = json.loads(args.params)
            except json.JSONDecodeError:
                print("Error: --params must be valid JSON.")
                return

        print(f"Queueing creation of {args.name} ({args.type})...")
        create_canary.delay(
            name=args.name,
            resource_type_str=args.type,
            interval_seconds=args.interval,
            environment_id_str=args.env,
            module_params=params,
            logging_resource_id_str=args.logging_id
        )
        print("Task queued.")

    elif args.command == "create-env":
        try:
            creds = json.loads(args.credentials)
            config = json.loads(args.config)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return

        db = SessionLocal()
        try:
            # Check for existing
            existing = db.query(CloudEnvironment).filter(CloudEnvironment.name == args.name).first()
            if existing:
                print(f"Updating existing environment: {existing.id}")
                existing.credentials = creds
                existing.config = config
                existing.provider_type = args.provider
                db.commit()
                print(f"Environment updated: {existing.id}")
            else:
                new_env = CloudEnvironment(
                    name=args.name,
                    provider_type=args.provider,
                    credentials=creds,
                    config=config
                )
                db.add(new_env)
                db.commit()
                print(f"Environment created: {new_env.id}")
        except Exception as e:
            print(f"Error creating environment: {e}")
        finally:
            db.close()

    elif args.command == "create-log":
        config = None
        if args.config:
            try:
                config = json.loads(args.config)
            except json.JSONDecodeError:
                print("Error: --config must be valid JSON.")
                return
        
        print(f"Queueing logging resource {args.name}...")
        create_logging_resource.delay(
            name=args.name,
            provider_type_str=args.type,
            environment_id_str=args.env,
            config=config
        )
        print("Task queued.")

    elif args.command == "list-logs":
        db = SessionLocal()
        try:
            logs = db.query(LoggingResource).all()
            print(f"{'ID':<38} | {'Name':<20} | {'Type':<15} | {'Env':<38}")
            print("-" * 120)
            for l in logs:
                print(f"{str(l.id):<38} | {l.name:<20} | {l.provider_type.value:<15} | {str(l.environment_id):<38}")
        finally:
            db.close()

    elif args.command == "scan_trails":
        scan_trails(args.env)

    elif args.command == "get-creds":
        db = SessionLocal()
        try:
             canary = db.query(CanaryResource).filter(CanaryResource.name == args.name).first()
             if not canary:
                 print(f"Error: Canary {args.name} not found.")
                 return
             
             if not canary.canary_credentials:
                 print("No credentials stored for this canary.")
             else:
                 print(json.dumps(canary.canary_credentials, indent=2))
        finally:
             db.close()
    
    elif args.command == "list":
        db = SessionLocal()
        try:
            canaries = db.query(CanaryResource).all()
            print(f"{'Name':<25} | {'Type':<20} | {'Status':<10} | {'Resource ID':<30} | {'Expires'}")
            print("-" * 110)
            for c in canaries:
                expires = c.expires_at.strftime("%Y-%m-%d %H:%M") if c.expires_at else "N/A"
                print(f"{c.name:<25} | {c.resource_type.value:<20} | {c.status.value:<10} | {str(c.current_resource_id):<30} | {expires}")
        finally:
            db.close()

    elif args.command == "delete":
        db = SessionLocal()
        try:
            # Try UUID first
            canary = None
            try:
                canary = db.query(CanaryResource).filter(CanaryResource.id == uuid.UUID(args.name_or_id)).first()
            except ValueError:
                pass
            
            if not canary:
                canary = db.query(CanaryResource).filter(CanaryResource.name == args.name_or_id).first()
            
            if not canary:
                print(f"Error: Canary {args.name_or_id} not found.")
                return
            
            print(f"Queueing deletion of {canary.name} ({canary.id})...")
            delete_canary.delay(str(canary.id))
            print("Task queued.")
        finally:
            db.close()

    elif args.command == "list-alerts":
        db = SessionLocal()
        try:
            query = db.query(Alert).join(CanaryResource).join(CloudEnvironment)
            
            if args.canary:
                # Try ID first
                try:
                    c_id = uuid.UUID(args.canary)
                    query = query.filter(CanaryResource.id == c_id)
                except ValueError:
                    query = query.filter(CanaryResource.name == args.canary)
            
            if args.env:
                try:
                    e_id = uuid.UUID(args.env)
                    query = query.filter(CloudEnvironment.id == e_id)
                except ValueError:
                    query = query.filter(CloudEnvironment.name == args.env)
            
            alerts = query.order_by(Alert.timestamp.desc()).all()
            
            print(f"{'Time (UTC)':<20} | {'Canary':<20} | {'Event':<25} | {'Source IP':<15} | {'Env':<15}")
            print("-" * 105)
            for a in alerts:
                t_str = a.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                print(f"{t_str:<20} | {a.canary.name:<20} | {a.event_name:<25} | {a.source_ip:<15} | {a.canary.environment.name:<15}")
        
        except Exception as e:
            print(f"Error listing alerts: {e}")
        finally:
            db.close()

    elif args.command == "trigger":
        db = SessionLocal()
        try:
            # Try UUID first
            canary = None
            try:
                canary = db.query(CanaryResource).filter(CanaryResource.id == uuid.UUID(args.name_or_id)).first()
            except ValueError:
                pass
            
            if not canary:
                canary = db.query(CanaryResource).filter(CanaryResource.name == args.name_or_id).first()
            
            if not canary:
                print(f"Error: Canary {args.name_or_id} not found.")
                return

            print(f"Initiating trigger for {canary.name} ({canary.resource_type.value})...")
            
            trigger = get_trigger(canary.resource_type)
            if not trigger:
                print(f"No trigger implementation found for type {canary.resource_type.value}")
                return
            
            success = trigger.execute(canary)
            if success:
                print("Trigger executed successfully. Events may take a few minutes to appear in logs.")
            else:
                print("Trigger execution failed. Check logs for details.")

        finally:
            db.close()

    elif args.command == "list-envs":
        db = SessionLocal()
        try:
            envs = db.query(CloudEnvironment).all()
            print(f"{'ID':<38} | {'Name':<20} | {'Provider'}")
            print("-" * 75)
            for e in envs:
                print(f"{str(e.id):<38} | {e.name:<20} | {e.provider_type}")
        finally:
            db.close()



    elif args.command == "help":
        print_custom_help()

    else:
        parser.print_help()


if __name__ == "__main__":
    run()
