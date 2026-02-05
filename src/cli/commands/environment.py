"""Environment management CLI commands."""
import json
from src.models import SessionLocal, CloudEnvironment
from ..utils import parse_json_arg


def register_commands(parent_subparsers):
    """Register the 'env' command group with its subcommands."""
    parser = parent_subparsers.add_parser(
        "env",
        help="Manage cloud environments",
        description="Create and manage cloud provider environments (AWS, GCP)."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # create
    parser_create = subparsers.add_parser("create", help="Create a cloud environment")
    parser_create.add_argument("name", help="Name of the environment")
    parser_create.add_argument("provider", help="Provider type (AWS, GCP)")
    parser_create.add_argument("--credentials", help="JSON string for credentials", required=True)
    parser_create.add_argument("--config", help="JSON string for configuration", default="{}")
    parser_create.set_defaults(func=handle_create)

    # list
    parser_list = subparsers.add_parser("list", help="List cloud environments")
    parser_list.set_defaults(func=handle_list)

    # sync
    parser_sync = subparsers.add_parser("sync", help="Sync environments from YAML config")
    parser_sync.add_argument("--dry-run", action="store_true",
                             help="Show what would be synced without making changes")
    parser_sync.add_argument("--force", action="store_true",
                             help="Overwrite existing DB entries with YAML config")
    parser_sync.add_argument("--validate", action="store_true",
                             help="Only validate environment variables, don't sync")
    parser_sync.set_defaults(func=handle_sync)


def handle_create(args):
    """Handle 'env create' command."""
    try:
        creds = json.loads(args.credentials)
        config = json.loads(args.config)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return

    db = SessionLocal()
    try:
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


def handle_list(args):
    """Handle 'env list' command."""
    db = SessionLocal()
    try:
        envs = db.query(CloudEnvironment).all()
        print(f"{'ID':<38} | {'Name':<20} | {'Provider':<10} | {'Status'}")
        print("-" * 90)
        for e in envs:
            status = e.status.value if e.status else "UNKNOWN"
            print(f"{str(e.id):<38} | {e.name:<20} | {e.provider_type:<10} | {status}")
    finally:
        db.close()


def handle_sync(args):
    """Handle 'env sync' command."""
    from src.environment_sync import sync_environments_from_yaml, validate_yaml_environments

    if args.validate:
        print("Validating environment variables...")
        result = validate_yaml_environments()

        for env_name, status in result["environments"].items():
            if status["valid"]:
                print(f"  ✓ {env_name}: OK")
            else:
                print(f"  ✗ {env_name}: {status['error']}")

        if result["valid"]:
            print("\nAll environments valid.")
        else:
            print("\nValidation failed. Set required environment variables before syncing.")
        return

    if args.dry_run:
        print("Dry run - no changes will be made\n")

    if args.force:
        print("WARNING: Force mode enabled - existing DB entries will be overwritten\n")

    result = sync_environments_from_yaml(dry_run=args.dry_run, force=args.force)

    if result["created"]:
        print(f"Created ({len(result['created'])}):")
        for name in result["created"]:
            print(f"  + {name}")

    if result["updated"]:
        print(f"Updated ({len(result['updated'])}):")
        for name in result["updated"]:
            print(f"  ~ {name}")

    if result["skipped"]:
        print(f"Skipped - already in DB ({len(result['skipped'])}):")
        for name in result["skipped"]:
            print(f"  - {name}")

    if result["errors"]:
        print(f"Errors ({len(result['errors'])}):")
        for err in result["errors"]:
            print(f"  ! {err['name']}: {err['error']}")

    if not any([result["created"], result["updated"], result["skipped"], result["errors"]]):
        print("No environments defined in config/environments.yaml")
