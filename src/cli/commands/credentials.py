"""Credential management CLI commands.

Economy of mechanism: Uses CredentialService for all operations.
"""
import json
from src.services import CredentialService


def register_commands(parent_subparsers):
    """Register the 'credentials' command group with its subcommands."""
    parser = parent_subparsers.add_parser(
        "credentials",
        help="Manage cloud credentials",
        description="Create and manage reusable cloud credentials for multi-account access."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # list
    parser_list = subparsers.add_parser("list", help="List all credentials")
    parser_list.set_defaults(func=handle_list)

    # add
    parser_add = subparsers.add_parser("add", help="Add a new credential")
    parser_add.add_argument("name", help="Name of the credential")
    parser_add.add_argument("provider", help="Provider type (AWS, GCP)")
    parser_add.add_argument("--auth-type", default="STATIC",
                            choices=["STATIC", "ASSUME_ROLE", "IMPERSONATE"],
                            help="Authentication type (default: STATIC)")
    parser_add.add_argument("--secrets", required=True,
                            help="JSON string for secrets (access keys, SA JSON, etc.)")
    parser_add.add_argument("--discovery-config",
                            help="JSON string for discovery configuration")
    parser_add.set_defaults(func=handle_add)

    # update
    parser_update = subparsers.add_parser("update", help="Update an existing credential")
    parser_update.add_argument("name", help="Name or ID of the credential")
    parser_update.add_argument("--auth-type", choices=["STATIC", "ASSUME_ROLE", "IMPERSONATE"],
                               help="Update authentication type")
    parser_update.add_argument("--secrets", help="JSON string for new secrets")
    parser_update.add_argument("--discovery-config", help="JSON string for discovery configuration")
    parser_update.set_defaults(func=handle_update)

    # remove
    parser_remove = subparsers.add_parser("remove", help="Remove a credential")
    parser_remove.add_argument("name", help="Name or ID of the credential")
    parser_remove.add_argument("--force", action="store_true",
                               help="Force removal even if accounts exist (deletes accounts too)")
    parser_remove.set_defaults(func=handle_remove)

    # get
    parser_get = subparsers.add_parser("get", help="Get credential details")
    parser_get.add_argument("name", help="Name or ID of the credential")
    parser_get.set_defaults(func=handle_get)

    # validate
    parser_validate = subparsers.add_parser("validate", help="Validate credential health")
    parser_validate.add_argument("name", help="Name or ID of the credential")
    parser_validate.set_defaults(func=handle_validate)

    # sync
    parser_sync = subparsers.add_parser("sync", help="Sync credentials from YAML config")
    parser_sync.add_argument("--dry-run", action="store_true",
                             help="Show what would be synced without making changes")
    parser_sync.add_argument("--force", action="store_true",
                             help="Overwrite existing DB entries with YAML config")
    parser_sync.add_argument("--validate", action="store_true",
                             help="Only validate environment variables, don't sync")
    parser_sync.set_defaults(func=handle_sync)


def handle_list(args):
    """Handle 'credentials list' command."""
    with CredentialService() as svc:
        result = svc.list()
        
        if not result.items:
            print("No credentials configured.")
            return
        
        print(f"{'Name':<25} | {'Provider':<8} | {'Auth Type':<12} | {'Accounts':<8} | {'Status'}")
        print("-" * 85)
        for c in result.items:
            status = c.status.value if c.status else "UNKNOWN"
            account_count = len(c.accounts) if c.accounts else 0
            print(f"{c.name:<25} | {c.provider:<8} | {c.auth_type.value:<12} | {account_count:<8} | {status}")


def handle_add(args):
    """Handle 'credentials add' command."""
    try:
        secrets = json.loads(args.secrets)
    except json.JSONDecodeError as e:
        print(f"Error parsing secrets JSON: {e}")
        return
    
    discovery_config = None
    if args.discovery_config:
        try:
            discovery_config = json.loads(args.discovery_config)
        except json.JSONDecodeError as e:
            print(f"Error parsing discovery-config JSON: {e}")
            return
    
    with CredentialService() as svc:
        result = svc.create(
            name=args.name,
            provider=args.provider,
            auth_type=args.auth_type,
            secrets=secrets,
            discovery_config=discovery_config
        )
        
        if result.success:
            print(f"Credential created: {result.data.name} ({result.data.id})")
        else:
            print(f"Error: {result.error}")


def handle_update(args):
    """Handle 'credentials update' command."""
    secrets = None
    if args.secrets:
        try:
            secrets = json.loads(args.secrets)
        except json.JSONDecodeError as e:
            print(f"Error parsing secrets JSON: {e}")
            return
    
    discovery_config = None
    if args.discovery_config:
        try:
            discovery_config = json.loads(args.discovery_config)
        except json.JSONDecodeError as e:
            print(f"Error parsing discovery-config JSON: {e}")
            return
    
    with CredentialService() as svc:
        result = svc.update(
            identifier=args.name,
            auth_type=args.auth_type,
            secrets=secrets,
            discovery_config=discovery_config
        )
        
        if result.success:
            print(f"Credential updated: {result.data.name}")
        else:
            print(f"Error: {result.error}")


def handle_remove(args):
    """Handle 'credentials remove' command."""
    with CredentialService() as svc:
        result = svc.delete(args.name, force=args.force)
        
        if result.success:
            print(f"Credential deleted: {args.name}")
        else:
            print(f"Error: {result.error}")


def handle_get(args):
    """Handle 'credentials get' command."""
    with CredentialService() as svc:
        result = svc.get(args.name)
        
        if not result.success:
            print(f"Error: {result.error}")
            return
        
        cred = result.data
        
        print(f"Name:           {cred.name}")
        print(f"ID:             {cred.id}")
        print(f"Provider:       {cred.provider}")
        print(f"Auth Type:      {cred.auth_type.value}")
        print(f"Status:         {cred.status.value if cred.status else 'UNKNOWN'}")
        print(f"Created:        {cred.created_at}")
        print(f"Accounts:       {len(cred.accounts) if cred.accounts else 0}")
        
        if cred.discovery_config:
            print(f"Discovery Config: {json.dumps(cred.discovery_config, indent=2)}")


def handle_validate(args):
    """Handle 'credentials validate' command."""
    with CredentialService() as svc:
        result = svc.validate(args.name)
        
        if not result.success:
            print(f"Error: {result.error}")
            return
        
        is_healthy, message = result.data
        if is_healthy:
            print(f"✓ {args.name}: {message}")
        else:
            print(f"✗ {args.name}: {message}")


def handle_sync(args):
    """Handle 'credentials sync' command."""
    with CredentialService() as svc:
        if args.validate:
            print("Validating environment variables...")
            result = svc.sync(validate_only=True)
            
            if not result.success:
                print(f"Error: {result.error}")
                return
            
            for cred_name, status in result.data["credentials"].items():
                if status["valid"]:
                    print(f"  ✓ {cred_name}: OK")
                else:
                    print(f"  ✗ {cred_name}: {status['error']}")
            
            if result.data["valid"]:
                print("\nAll credentials valid.")
            else:
                print("\nValidation failed. Set required environment variables before syncing.")
            return
        
        if args.dry_run:
            print("Dry run - no changes will be made\n")
        
        if args.force:
            print("WARNING: Force mode enabled - existing DB entries will be overwritten\n")
        
        result = svc.sync(dry_run=args.dry_run, force=args.force)
        
        if not result.success:
            print(f"Error: {result.error}")
            return
        
        data = result.data
        
        if data.get("created_credentials"):
            print(f"Created credentials ({len(data['created_credentials'])}):")
            for name in data["created_credentials"]:
                print(f"  + {name}")
        
        if data.get("created_accounts"):
            print(f"Created accounts ({len(data['created_accounts'])}):")
            for name in data["created_accounts"]:
                print(f"  + {name}")
        
        if data.get("updated"):
            print(f"Updated ({len(data['updated'])}):")
            for name in data["updated"]:
                print(f"  ~ {name}")
        
        if data.get("skipped"):
            print(f"Skipped - already in DB ({len(data['skipped'])}):")
            for name in data["skipped"]:
                print(f"  - {name}")
        
        if data.get("errors"):
            print(f"Errors ({len(data['errors'])}):")
            for err in data["errors"]:
                print(f"  ! {err['name']}: {err['error']}")
        
        if not any([data.get("created_credentials"), data.get("created_accounts"),
                    data.get("updated"), data.get("skipped"), data.get("errors")]):
            print("No credentials defined in config/credentials.yaml")
