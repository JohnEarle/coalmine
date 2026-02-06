"""Account management CLI commands.

Economy of mechanism: Uses AccountService for all operations.
"""
import json
from src.services import AccountService


def register_commands(parent_subparsers):
    """Register the 'accounts' command group with its subcommands."""
    parser = parent_subparsers.add_parser(
        "accounts",
        help="Manage cloud accounts",
        description="Create and manage cloud accounts (deployment targets) linked to credentials."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # list
    parser_list = subparsers.add_parser("list", help="List all accounts")
    parser_list.add_argument("--credential", help="Filter by credential name or ID")
    parser_list.add_argument("--provider", help="Filter by provider (AWS, GCP)")
    parser_list.set_defaults(func=handle_list)

    # add
    parser_add = subparsers.add_parser("add", help="Add a new account")
    parser_add.add_argument("name", help="Name of the account")
    parser_add.add_argument("credential", help="Name or ID of the credential")
    parser_add.add_argument("account_id", help="Cloud account ID (AWS account ID or GCP project ID)")
    parser_add.add_argument("--role-override", help="Override default role/service account")
    parser_add.add_argument("--metadata", help="JSON string for metadata")
    parser_add.set_defaults(func=handle_add)

    # update
    parser_update = subparsers.add_parser("update", help="Update an existing account")
    parser_update.add_argument("name", help="Name or ID of the account")
    parser_update.add_argument("--role-override", help="Update role override")
    parser_update.add_argument("--metadata", help="JSON string for metadata")
    parser_update.set_defaults(func=handle_update)

    # enable
    parser_enable = subparsers.add_parser("enable", help="Enable an account")
    parser_enable.add_argument("name", help="Name or ID of the account")
    parser_enable.set_defaults(func=handle_enable)

    # disable
    parser_disable = subparsers.add_parser("disable", help="Disable an account")
    parser_disable.add_argument("name", help="Name or ID of the account")
    parser_disable.set_defaults(func=handle_disable)

    # remove
    parser_remove = subparsers.add_parser("remove", help="Remove an account")
    parser_remove.add_argument("name", help="Name or ID of the account")
    parser_remove.set_defaults(func=handle_remove)

    # get
    parser_get = subparsers.add_parser("get", help="Get account details")
    parser_get.add_argument("name", help="Name or ID of the account")
    parser_get.set_defaults(func=handle_get)

    # validate
    parser_validate = subparsers.add_parser("validate", help="Validate account health")
    parser_validate.add_argument("name", help="Name or ID of the account")
    parser_validate.set_defaults(func=handle_validate)


def handle_list(args):
    """Handle 'accounts list' command."""
    with AccountService() as svc:
        result = svc.list(credential=args.credential, provider=args.provider)
        
        if not result.items:
            print("No accounts configured.")
            return
        
        print(f"{'Name':<20} | {'Account ID':<20} | {'Credential':<18} | {'Enabled':<8} | {'Source'}")
        print("-" * 95)
        for a in result.items:
            cred_name = a.credential.name if a.credential else "N/A"
            enabled = "Yes" if a.is_enabled == "true" else "No"
            source = a.source.value if a.source else "MANUAL"
            print(f"{a.name:<20} | {a.account_id:<20} | {cred_name:<18} | {enabled:<8} | {source}")


def handle_add(args):
    """Handle 'accounts add' command."""
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error parsing metadata JSON: {e}")
            return
    
    with AccountService() as svc:
        result = svc.create(
            name=args.name,
            credential_id=args.credential,
            account_id=args.account_id,
            role_override=args.role_override,
            metadata=metadata
        )
        
        if result.success:
            print(f"Account created: {result.data.name} ({result.data.id})")
        else:
            print(f"Error: {result.error}")


def handle_update(args):
    """Handle 'accounts update' command."""
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error parsing metadata JSON: {e}")
            return
    
    with AccountService() as svc:
        result = svc.update(
            identifier=args.name,
            role_override=args.role_override,
            metadata=metadata
        )
        
        if result.success:
            print(f"Account updated: {result.data.name}")
        else:
            print(f"Error: {result.error}")


def handle_enable(args):
    """Handle 'accounts enable' command."""
    with AccountService() as svc:
        result = svc.enable(args.name)
        
        if result.success:
            print(f"Account enabled: {result.data.name}")
        else:
            print(f"Error: {result.error}")


def handle_disable(args):
    """Handle 'accounts disable' command."""
    with AccountService() as svc:
        result = svc.disable(args.name)
        
        if result.success:
            print(f"Account disabled: {result.data.name}")
        else:
            print(f"Error: {result.error}")


def handle_remove(args):
    """Handle 'accounts remove' command."""
    with AccountService() as svc:
        result = svc.delete(args.name)
        
        if result.success:
            print(f"Account deleted: {args.name}")
        else:
            print(f"Error: {result.error}")


def handle_get(args):
    """Handle 'accounts get' command."""
    with AccountService() as svc:
        result = svc.get(args.name)
        
        if not result.success:
            print(f"Error: {result.error}")
            return
        
        account = result.data
        cred = account.credential
        
        print(f"Name:           {account.name}")
        print(f"ID:             {account.id}")
        print(f"Account ID:     {account.account_id}")
        print(f"Credential:     {cred.name if cred else 'N/A'}")
        print(f"Provider:       {cred.provider if cred else 'N/A'}")
        print(f"Source:         {account.source.value if account.source else 'MANUAL'}")
        print(f"Enabled:        {'Yes' if account.is_enabled == 'true' else 'No'}")
        print(f"Status:         {account.status.value if account.status else 'UNKNOWN'}")
        print(f"Created:        {account.created_at}")
        
        if account.role_override:
            print(f"Role Override:  {account.role_override}")
        
        if account.account_metadata:
            print(f"Metadata:       {json.dumps(account.account_metadata, indent=2)}")


def handle_validate(args):
    """Handle 'accounts validate' command."""
    with AccountService() as svc:
        result = svc.validate(args.name)
        
        if not result.success:
            print(f"Error: {result.error}")
            return
        
        is_healthy, message = result.data
        if is_healthy:
            print(f"✓ {args.name}: {message}")
        else:
            print(f"✗ {args.name}: {message}")
