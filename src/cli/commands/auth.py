"""Auth management CLI commands.

Provides lifecycle management for API keys, sessions, and RBAC.
"""
from src.services import AuthService


def register_commands(parent_subparsers):
    """Register the 'auth' command group with its subcommands."""
    parser = parent_subparsers.add_parser(
        "auth",
        help="Manage authentication",
        description="Manage API keys, sessions, and RBAC policies."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # =========================================================================
    # API Key Commands
    # =========================================================================
    
    # key (sub-group)
    parser_key = subparsers.add_parser("key", help="Manage API keys")
    key_subparsers = parser_key.add_subparsers(dest="key_action", help="Key action")
    
    # key list
    parser_key_list = key_subparsers.add_parser("list", help="List all API keys")
    parser_key_list.set_defaults(func=handle_key_list)
    
    # key create
    parser_key_create = key_subparsers.add_parser("create", help="Create a new API key")
    parser_key_create.add_argument("name", help="Unique name for the key")
    parser_key_create.add_argument("--permissions", nargs="+", required=True,
                                   help="Permissions: read, write, admin")
    parser_key_create.add_argument("--scopes", nargs="+", required=True,
                                   help="Scopes: canaries, credentials, all, etc.")
    parser_key_create.add_argument("--description", default="", help="Description")
    parser_key_create.add_argument("--expires", help="Expiration (ISO 8601 datetime)")
    parser_key_create.add_argument("--ip-allowlist", nargs="+", help="Allowed IPs/CIDRs")
    parser_key_create.add_argument("--owner", help="Owner username")
    parser_key_create.set_defaults(func=handle_key_create)
    
    # key revoke
    parser_key_revoke = key_subparsers.add_parser("revoke", help="Revoke an API key")
    parser_key_revoke.add_argument("name", help="Name of the key to revoke")
    parser_key_revoke.set_defaults(func=handle_key_revoke)
    
    # =========================================================================
    # Session Commands
    # =========================================================================
    
    # session (sub-group)
    parser_session = subparsers.add_parser("session", help="Manage sessions")
    session_subparsers = parser_session.add_subparsers(dest="session_action", help="Session action")
    
    # session list
    parser_session_list = session_subparsers.add_parser("list", help="List active sessions")
    parser_session_list.set_defaults(func=handle_session_list)
    
    # session revoke
    parser_session_revoke = session_subparsers.add_parser("revoke", help="Revoke a session")
    parser_session_revoke.add_argument("prefix", help="Session ID prefix (first 8+ chars)")
    parser_session_revoke.set_defaults(func=handle_session_revoke)
    
    # =========================================================================
    # RBAC Commands
    # =========================================================================
    
    # rbac (sub-group)
    parser_rbac = subparsers.add_parser("rbac", help="Manage RBAC policies")
    rbac_subparsers = parser_rbac.add_subparsers(dest="rbac_action", help="RBAC action")
    
    # rbac reload
    parser_rbac_reload = rbac_subparsers.add_parser("reload", help="Reload RBAC policies")
    parser_rbac_reload.set_defaults(func=handle_rbac_reload)


# =============================================================================
# Handlers
# =============================================================================

def handle_key_list(args):
    """Handle 'auth key list' command."""
    with AuthService() as svc:
        result = svc.list_api_keys()
        
        if not result.items:
            print("No API keys configured.")
            return
        
        print(f"{'Name':<20} | {'Permissions':<15} | {'Scopes':<20} | {'Owner':<10} | {'Active'}")
        print("-" * 80)
        for key in result.items:
            perms = ",".join(key.permissions)
            scopes = ",".join(key.scopes[:2]) + ("..." if len(key.scopes) > 2 else "")
            owner = key.owner or "-"
            active = "Yes" if key.is_active else "EXPIRED"
            print(f"{key.name:<20} | {perms:<15} | {scopes:<20} | {owner:<10} | {active}")


def handle_key_create(args):
    """Handle 'auth key create' command."""
    with AuthService() as svc:
        result = svc.create_api_key(
            name=args.name,
            permissions=args.permissions,
            scopes=args.scopes,
            description=args.description,
            expires_at=args.expires,
            ip_allowlist=args.ip_allowlist,
            owner=args.owner
        )
        
        if result.success:
            print(f"\n✓ API key '{args.name}' created successfully.\n")
            print(f"  Key: {result.data['key']}")
            print(f"\n  ⚠️  Save this key securely - it cannot be retrieved later.\n")
        else:
            print(f"Error: {result.error}")


def handle_key_revoke(args):
    """Handle 'auth key revoke' command."""
    with AuthService() as svc:
        result = svc.revoke_api_key(args.name)
        
        if result.success:
            print(f"✓ API key '{args.name}' revoked.")
        else:
            print(f"Error: {result.error}")


def handle_session_list(args):
    """Handle 'auth session list' command."""
    with AuthService() as svc:
        result = svc.list_sessions()
        
        if not result.items:
            print("No active sessions.")
            return
        
        print(f"{'Session ID':<12} | {'Username':<15} | {'Role':<10} | {'Auth Method'}")
        print("-" * 60)
        for session in result.items:
            print(f"{session.session_id:<12} | {session.username:<15} | {session.role:<10} | {session.auth_method}")


def handle_session_revoke(args):
    """Handle 'auth session revoke' command."""
    with AuthService() as svc:
        result = svc.revoke_session(args.prefix)
        
        if result.success:
            print(f"✓ Revoked {result.data['revoked_count']} session(s).")
        else:
            print(f"Error: {result.error}")


def handle_rbac_reload(args):
    """Handle 'auth rbac reload' command."""
    with AuthService() as svc:
        result = svc.reload_rbac()
        
        if result.success:
            print(f"✓ RBAC policies reloaded ({result.data['policy_count']} rules).")
        else:
            print(f"Error: {result.error}")
