"""Logging resource CLI commands.

Economy of mechanism: Uses LoggingResourceService for all operations.
"""
import json
from src.services import LoggingResourceService


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
    parser_create.add_argument("--account", help="Account name or ID", required=True)
    parser_create.add_argument("--config", help="JSON string for configuration")
    parser_create.set_defaults(func=handle_create)

    # list
    parser_list = subparsers.add_parser("list", help="List logging resources")
    parser_list.set_defaults(func=handle_list)

    # scan (was scan_trails)
    parser_scan = subparsers.add_parser("scan", help="Scan existing CloudTrails/LogGroups")
    parser_scan.add_argument("--account", help="Account name or ID", required=True)
    parser_scan.set_defaults(func=handle_scan)


def handle_create(args):
    """Handle 'logs create' command."""
    config = None
    if args.config:
        try:
            config = json.loads(args.config)
        except json.JSONDecodeError as e:
            print(f"Error parsing config JSON: {e}")
            return
    
    print(f"Queueing logging resource {args.name}...")
    
    with LoggingResourceService() as svc:
        result = svc.create(
            name=args.name,
            provider_type=args.type,
            account_id=args.account,
            config=config
        )
        
        if result.success:
            print("Task queued.")
        else:
            print(f"Error: {result.error}")


def handle_list(args):
    """Handle 'logs list' command."""
    with LoggingResourceService() as svc:
        result = svc.list()
        
        if not result.items:
            print("No logging resources configured.")
            return
        
        print(f"{'ID':<38} | {'Name':<20} | {'Type':<15} | {'Account':<20} | {'Status'}")
        print("-" * 120)
        for log in result.items:
            account_name = log.account.name if log.account else "N/A"
            print(f"{str(log.id):<38} | {log.name:<20} | {log.provider_type.value:<15} | {account_name:<20} | {log.status.value}")


def handle_scan(args):
    """Handle 'logs scan' command - list available CloudTrails and LogGroups."""
    with LoggingResourceService() as svc:
        result = svc.scan(args.account)
        
        if not result.success:
            print(f"Error: {result.error}")
            return
        
        data = result.data
        region = data.get("region", "unknown")
        
        print(f"--- CloudTrails in {region} ---")
        for t in data.get("trails", []):
            print(f"- Name: {t['name']}")
            print(f"  ARN: {t['arn']}")
            print(f"  Log Group: {t['log_group_arn']}")
            print("")
        
        print(f"--- CloudWatch Log Groups in {region} ---")
        for lg in data.get("log_groups", []):
            print(f"- Name: {lg['name']}")
            print(f"  ARN: {lg['arn']}")
