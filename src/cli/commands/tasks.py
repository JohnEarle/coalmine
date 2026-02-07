"""Task log CLI commands.

Economy of mechanism: Uses TaskService for all operations.
"""
from src.services import TaskService


def register_commands(parent_subparsers):
    """Register the 'task' command group with its subcommands."""
    parser = parent_subparsers.add_parser(
        "task",
        help="View async task status and history",
        description="List and inspect asynchronous task logs."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # list
    parser_list = subparsers.add_parser("list", help="List task logs")
    parser_list.add_argument(
        "--all", dest="include_system", action="store_true",
        help="Include system-triggered tasks (rotations, monitoring, etc.)"
    )
    parser_list.set_defaults(func=handle_list)

    # get
    parser_get = subparsers.add_parser("get", help="Get details for a specific task")
    parser_get.add_argument("task_id", help="Task UUID or Celery task ID")
    parser_get.set_defaults(func=handle_get)


def handle_list(args):
    """Handle 'task list' command."""
    with TaskService() as svc:
        result = svc.list(include_system=args.include_system)

        if not result.items:
            print("No tasks found.")
            return

        print(f"{'Task':<25} | {'Status':<10} | {'Source':<8} | {'Canary':<20} | {'Created'}")
        print("-" * 100)
        for t in result.items:
            canary_name = t.canary.name if t.canary else "-"
            created = t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "N/A"
            print(f"{t.task_name:<25} | {t.status.value:<10} | {t.source:<8} | {canary_name:<20} | {created}")


def handle_get(args):
    """Handle 'task get' command."""
    with TaskService() as svc:
        result = svc.get(args.task_id)

        if not result.success:
            print(f"Error: {result.error}")
            return

        t = result.data
        print(f"  Task ID:    {t.celery_task_id}")
        print(f"  Name:       {t.task_name}")
        print(f"  Source:     {t.source}")
        print(f"  Status:     {t.status.value}")
        if t.canary:
            print(f"  Canary:     {t.canary.name}")
        if t.created_at:
            print(f"  Created:    {t.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if t.started_at:
            print(f"  Started:    {t.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if t.finished_at:
            print(f"  Finished:   {t.finished_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if t.error:
            print(f"  Error:      {t.error}")
        if t.result_data:
            import json
            print(f"  Result:     {json.dumps(t.result_data, indent=2)}")
