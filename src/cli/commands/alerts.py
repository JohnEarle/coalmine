"""Alert management CLI commands.

Economy of mechanism: Uses AlertService for all operations.
"""
from src.services import AlertService


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
    parser_list.add_argument("--account", help="Filter by Account Name or ID")
    parser_list.set_defaults(func=handle_list)


def handle_list(args):
    """Handle 'alerts list' command."""
    with AlertService() as svc:
        result = svc.list(canary=args.canary, account=args.account)
        
        if not result.items:
            print("No alerts found.")
            return
        
        print(f"{'Time (UTC)':<20} | {'Canary':<20} | {'Event':<25} | {'Source IP':<15} | {'Account':<15}")
        print("-" * 105)
        for a in result.items:
            t_str = a.timestamp.strftime("%Y-%m-%d %H:%M:%S") if a.timestamp else "N/A"
            canary_name = a.canary.name if a.canary else "N/A"
            account_name = a.canary.account.name if a.canary and a.canary.account else "N/A"
            print(f"{t_str:<20} | {canary_name:<20} | {a.event_name:<25} | {a.source_ip:<15} | {account_name:<15}")
