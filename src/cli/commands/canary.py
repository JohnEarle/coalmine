"""Canary management CLI commands."""
import json
from src.tasks import create_canary as create_canary_task, delete_canary as delete_canary_task
from src.models import SessionLocal, CanaryResource
from src.triggers import get_trigger
from ..utils import resolve_canary, parse_json_arg


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
    parser_create.add_argument("--env", help="Environment ID (UUID)", required=True)
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
    params = parse_json_arg(args.params, "params") if args.params else None

    print(f"Queueing creation of {args.name} ({args.type})...")
    create_canary_task.delay(
        name=args.name,
        resource_type_str=args.type,
        interval_seconds=args.interval,
        environment_id_str=args.env,
        module_params=params,
        logging_resource_id_str=args.logging_id
    )
    print("Task queued.")


def handle_list(args):
    """Handle 'canary list' command."""
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


def handle_delete(args):
    """Handle 'canary delete' command."""
    db = SessionLocal()
    try:
        canary = resolve_canary(db, args.name_or_id)
        if not canary:
            print(f"Error: Canary {args.name_or_id} not found.")
            return

        print(f"Queueing deletion of {canary.name} ({canary.id})...")
        delete_canary_task.delay(str(canary.id))
        print("Task queued.")
    finally:
        db.close()


def handle_creds(args):
    """Handle 'canary creds' command."""
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


def handle_trigger(args):
    """Handle 'canary trigger' command."""
    db = SessionLocal()
    try:
        canary = resolve_canary(db, args.name_or_id)
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
