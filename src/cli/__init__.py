"""
Coalmine CLI - Command Line Interface

This package provides the CLI for managing canary resources, cloud environments,
logging configurations, and alerts.

Command structure: coalmine <resource> <action> [options]
Resources: canary, env, logs, alerts
"""
import sys
import os
import argparse

# Ensure root is in path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .commands import canary, environment, logging_cmd, alerts
from .utils import print_custom_help


def run():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Coalmine CLI - Canary token management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Resources:
  canary    Manage canary resources (create, list, delete, trigger)
  env       Manage cloud environments (create, list, sync)
  logs      Manage logging resources (create, list, scan)
  alerts    View security alerts

Examples:
  coalmine canary list
  coalmine canary create my-canary AWS_IAM_USER --env <id> --logging-id <id>
  coalmine env sync --dry-run
  coalmine alerts list --canary my-canary
"""
    )
    subparsers = parser.add_subparsers(dest="resource", help="Resource to manage")

    # Register command groups from each module
    canary.register_commands(subparsers)
    environment.register_commands(subparsers)
    logging_cmd.register_commands(subparsers)
    alerts.register_commands(subparsers)

    # Help command
    subparsers.add_parser("help", help="Show detailed usage guide")

    args = parser.parse_args()

    if args.resource == "help":
        print_custom_help()
    elif hasattr(args, 'func'):
        args.func(args)
    elif args.resource:
        # User specified resource but no action - show resource help
        parser.parse_args([args.resource, '--help'])
    else:
        parser.print_help()


if __name__ == "__main__":
    run()
