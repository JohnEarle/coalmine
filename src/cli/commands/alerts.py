"""Alert management CLI commands."""
import uuid as uuid_module
from src.models import SessionLocal, Alert, CanaryResource, CloudEnvironment


def register_commands(parent_subparsers):
    """Register the 'alerts' command group with its subcommands."""
    parser = parent_subparsers.add_parser(
        "alerts",
        help="View security alerts",
        description="List and filter security alerts from canary detections."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # list
    parser_list = subparsers.add_parser("list", help="List alerts")
    parser_list.add_argument("--canary", help="Filter by Canary Name or ID")
    parser_list.add_argument("--env", help="Filter by Environment Name or ID")
    parser_list.set_defaults(func=handle_list)


def handle_list(args):
    """Handle 'alerts list' command."""
    db = SessionLocal()
    try:
        query = db.query(Alert).join(CanaryResource).join(CloudEnvironment)

        if args.canary:
            try:
                c_id = uuid_module.UUID(args.canary)
                query = query.filter(CanaryResource.id == c_id)
            except ValueError:
                query = query.filter(CanaryResource.name == args.canary)

        if args.env:
            try:
                e_id = uuid_module.UUID(args.env)
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
