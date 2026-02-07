"""User management CLI commands.

Provides lifecycle management for user accounts and roles.
"""
from src.services import UserService


def register_commands(parent_subparsers):
    """Register the 'user' command group with its subcommands."""
    parser = parent_subparsers.add_parser(
        "user",
        help="Manage users",
        description="Manage user accounts and roles."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # list
    parser_list = subparsers.add_parser("list", help="List all users")
    parser_list.set_defaults(func=handle_list)

    # create
    parser_create = subparsers.add_parser("create", help="Create a new user")
    parser_create.add_argument("email", help="User email address")
    parser_create.add_argument("--password", required=True, help="Password")
    parser_create.add_argument("--role", default="viewer", help="Role (default: viewer)")
    parser_create.add_argument("--display-name", help="Display name")
    parser_create.add_argument("--superuser", action="store_true", help="Grant superuser")
    parser_create.set_defaults(func=handle_create)

    # update
    parser_update = subparsers.add_parser("update", help="Update a user")
    parser_update.add_argument("identifier", help="User UUID or email")
    parser_update.add_argument("--role", help="New role")
    parser_update.add_argument("--display-name", help="New display name")
    parser_update.add_argument("--active", choices=["true", "false"], help="Activate/deactivate")
    parser_update.add_argument("--superuser", choices=["true", "false"], help="Grant/revoke superuser")
    parser_update.set_defaults(func=handle_update)

    # delete
    parser_delete = subparsers.add_parser("delete", help="Delete a user")
    parser_delete.add_argument("identifier", help="User UUID or email")
    parser_delete.set_defaults(func=handle_delete)

    # roles
    parser_roles = subparsers.add_parser("roles", help="List available roles")
    parser_roles.set_defaults(func=handle_roles)


# =============================================================================
# Handlers
# =============================================================================

def handle_list(args):
    """Handle 'user list' command."""
    with UserService() as svc:
        result = svc.list()

        if not result.items:
            print("No users found.")
            return

        print(f"{'Email':<30} | {'Role':<12} | {'Active':<8} | {'Superuser':<10} | {'Display Name'}")
        print("-" * 90)
        for u in result.items:
            active = "Yes" if u.is_active else "No"
            su = "Yes" if u.is_superuser else "-"
            name = u.display_name or "-"
            print(f"{u.email:<30} | {u.role:<12} | {active:<8} | {su:<10} | {name}")


def handle_create(args):
    """Handle 'user create' command."""
    with UserService() as svc:
        result = svc.create(
            email=args.email,
            password=args.password,
            role=args.role,
            display_name=args.display_name,
            is_superuser=args.superuser,
        )

        if result.success:
            print(f"✓ User '{args.email}' created (role={args.role}).")
        else:
            print(f"Error: {result.error}")


def handle_update(args):
    """Handle 'user update' command."""
    kwargs = {}
    if args.role:
        kwargs["role"] = args.role
    if args.display_name:
        kwargs["display_name"] = args.display_name
    if args.active is not None:
        kwargs["is_active"] = args.active == "true"
    if args.superuser is not None:
        kwargs["is_superuser"] = args.superuser == "true"

    if not kwargs:
        print("Error: No updates specified. Use --role, --display-name, --active, or --superuser.")
        return

    with UserService() as svc:
        result = svc.update(args.identifier, **kwargs)

        if result.success:
            print(f"✓ User '{args.identifier}' updated.")
        else:
            print(f"Error: {result.error}")


def handle_delete(args):
    """Handle 'user delete' command."""
    with UserService() as svc:
        result = svc.delete(args.identifier)

        if result.success:
            print(f"✓ User '{result.data['email']}' deleted.")
        else:
            print(f"Error: {result.error}")


def handle_roles(args):
    """Handle 'user roles' command."""
    with UserService() as svc:
        result = svc.list_roles()

        if not result.items:
            print("No roles configured.")
            return

        print("Available roles (most → least privileged):")
        for i, role in enumerate(result.items, 1):
            print(f"  {i}. {role}")
