"""Canary management CLI commands.

Economy of mechanism: Uses CanaryService for all operations.
"""
import json
from src.services import CanaryService


def register_commands(parent_subparsers):
    """Register the 'canary' command group with its subcommands."""
    parser = parent_subparsers.add_parser(
        "canary",
        help="Manage canary resources",
        description="Create, list, delete, and manage canary token resources."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # create
    parser_create = subparsers.add_parser("create", help="Create a new canary")
    parser_create.add_argument("name", help="Logical name of the canary")
    parser_create.add_argument("type", help="Resource type (AWS_IAM_USER, AWS_BUCKET, GCP_SERVICE_ACCOUNT, GCP_BUCKET)")
    parser_create.add_argument("--interval", type=int, default=0,
                               help="Rotation interval in seconds (0 for static)")
    parser_create.add_argument("--account", help="Account name or ID (deployment target)", required=True)
    parser_create.add_argument("--logging-id", help="Logging Resource ID (UUID)", required=True)
    parser_create.add_argument("--params", help="JSON string for module parameters")
    parser_create.set_defaults(func=handle_create)

    # list
    parser_list = subparsers.add_parser("list", help="List all canaries")
    parser_list.set_defaults(func=handle_list)

    # delete
    parser_delete = subparsers.add_parser("delete", help="Delete a canary")
    parser_delete.add_argument("name_or_id", help="Name or ID of the canary")
    parser_delete.set_defaults(func=handle_delete)

    # creds (was get-creds)
    parser_creds = subparsers.add_parser("creds", help="Get credentials for a canary")
    parser_creds.add_argument("name", help="Name of the canary")
    parser_creds.set_defaults(func=handle_creds)

    # trigger
    parser_trigger = subparsers.add_parser("trigger", help="Trigger a test alert")
    parser_trigger.add_argument("name_or_id", help="Name or ID of the canary")
    parser_trigger.set_defaults(func=handle_trigger)


def handle_create(args):
    """Handle 'canary create' command."""
    params = None
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"Error parsing params JSON: {e}")
            return
    
    print(f"Queueing creation of {args.name} ({args.type})...")
    
    with CanaryService() as svc:
        result = svc.create(
            name=args.name,
            resource_type=args.type,
            account_id=args.account,
            logging_id=args.logging_id,
            interval=args.interval,
            params=params
        )
        
        if result.success:
            print("Task queued.")
        else:
            print(f"Error: {result.error}")


def handle_list(args):
    """Handle 'canary list' command."""
    with CanaryService() as svc:
        result = svc.list()
        
        if not result.items:
            print("No canaries configured.")
            return
        
        print(f"{'Name':<25} | {'Type':<20} | {'Account':<20} | {'Status':<10} | {'Expires'}")
        print("-" * 100)
        for c in result.items:
            expires = c.expires_at.strftime("%Y-%m-%d %H:%M") if c.expires_at else "N/A"
            account_name = c.account.name if c.account else "N/A"
            print(f"{c.name:<25} | {c.resource_type.value:<20} | {account_name:<20} | {c.status.value:<10} | {expires}")


def handle_delete(args):
    """Handle 'canary delete' command."""
    with CanaryService() as svc:
        # First check if it exists
        get_result = svc.get(args.name_or_id)
        if not get_result.success:
            print(f"Error: Canary {args.name_or_id} not found.")
            return
        
        canary = get_result.data
        print(f"Queueing deletion of {canary.name} ({canary.id})...")
        
        result = svc.delete(args.name_or_id)
        
        if result.success:
            print("Task queued.")
        else:
            print(f"Error: {result.error}")


def handle_creds(args):
    """Handle 'canary creds' command."""
    with CanaryService() as svc:
        result = svc.get_credentials(args.name)
        
        if not result.success:
            print(f"Error: {result.error}")
            return
        
        creds = result.data.get("credentials")
        if not creds:
            print("No credentials stored for this canary.")
        else:
            print(json.dumps(creds, indent=2))


def handle_trigger(args):
    """Handle 'canary trigger' command."""
    with CanaryService() as svc:
        get_result = svc.get(args.name_or_id)
        if not get_result.success:
            print(f"Error: Canary {args.name_or_id} not found.")
            return
        
        canary = get_result.data
        print(f"Initiating trigger for {canary.name} ({canary.resource_type.value})...")
        
        result = svc.trigger(args.name_or_id)
        
        if result.success:
            if result.data.get("success"):
                print("Trigger executed successfully. Events may take a few minutes to appear in logs.")
            else:
                print("Trigger execution failed. Check logs for details.")
        else:
            print(f"Error: {result.error}")
