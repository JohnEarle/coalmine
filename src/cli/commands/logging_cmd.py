"""Logging resource CLI commands."""
import json
import boto3
import uuid as uuid_module
from src.tasks import create_logging_resource
from src.models import SessionLocal, LoggingResource, CloudEnvironment
from ..utils import parse_json_arg


def register_commands(parent_subparsers):
    """Register the 'logs' command group with its subcommands."""
    parser = parent_subparsers.add_parser(
        "logs",
        help="Manage logging resources",
        description="Create and manage logging resources (CloudTrail, GCP Audit Sink)."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # create
    parser_create = subparsers.add_parser("create", help="Create a logging resource")
    parser_create.add_argument("name", help="Name of the logging resource")
    parser_create.add_argument("type", help="Type: AWS_CLOUDTRAIL, GCP_AUDIT_SINK")
    parser_create.add_argument("--env", help="Environment ID (UUID)", required=True)
    parser_create.add_argument("--config", help="JSON string for configuration")
    parser_create.set_defaults(func=handle_create)

    # list
    parser_list = subparsers.add_parser("list", help="List logging resources")
    parser_list.set_defaults(func=handle_list)

    # scan (was scan_trails)
    parser_scan = subparsers.add_parser("scan", help="Scan existing CloudTrails/LogGroups")
    parser_scan.add_argument("--env", help="Environment ID (UUID)", required=True)
    parser_scan.set_defaults(func=handle_scan)


def handle_create(args):
    """Handle 'logs create' command."""
    config = parse_json_arg(args.config, "config") if args.config else None

    print(f"Queueing logging resource {args.name}...")
    create_logging_resource.delay(
        name=args.name,
        provider_type_str=args.type,
        environment_id_str=args.env,
        config=config
    )
    print("Task queued.")


def handle_list(args):
    """Handle 'logs list' command."""
    db = SessionLocal()
    try:
        logs = db.query(LoggingResource).all()
        print(f"{'ID':<38} | {'Name':<20} | {'Type':<15} | {'Status':<10} | {'Env':<38}")
        print("-" * 135)
        for log in logs:
            print(f"{str(log.id):<38} | {log.name:<20} | {log.provider_type.value:<15} | {log.status.value:<10} | {str(log.environment_id):<38}")
    finally:
        db.close()


def handle_scan(args):
    """Handle 'logs scan' command - list available CloudTrails and LogGroups."""
    db = SessionLocal()
    try:
        env_obj = db.query(CloudEnvironment).filter(
            CloudEnvironment.id == uuid_module.UUID(args.env)
        ).first()
        if not env_obj:
            print(f"Error: Environment {args.env} not found.")
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
                response = logs.describe_log_groups(limit=50)
                for lg in response.get("logGroups", []):
                    print(f"- Name: {lg['logGroupName']}")
                    print(f"  ARN: {lg['arn']}")
            except Exception as e:
                print(f"Error scanning logs: {e}")

        else:
            print("Only AWS supported for logs scan currently.")

    finally:
        db.close()
