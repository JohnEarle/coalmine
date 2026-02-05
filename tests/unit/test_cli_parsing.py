"""Unit tests for CLI argument parsing."""
import pytest
from unittest.mock import patch, MagicMock
import argparse
import sys


class TestCLIParsing:
    """Test CLI argument parsing with mocked handlers."""
    
    @pytest.fixture
    def cli_parser(self):
        """Create a CLI parser for testing."""
        # Import here to avoid import-time side effects
        with patch.dict(sys.modules, {
            'src.models': MagicMock(),
            'src.tasks': MagicMock(),
            'src.triggers': MagicMock(),
            'src.environment_sync': MagicMock(),
            'boto3': MagicMock(),
        }):
            from src.cli import run
            from src.cli.commands import canary, environment, logging_cmd, alerts
            
            parser = argparse.ArgumentParser(description="Test CLI")
            subparsers = parser.add_subparsers(dest="resource")
            
            canary.register_commands(subparsers)
            environment.register_commands(subparsers)
            logging_cmd.register_commands(subparsers)
            alerts.register_commands(subparsers)
            
            return parser

    # ========== Canary Commands ==========
    
    @pytest.mark.unit
    def test_canary_list_parses(self, cli_parser):
        """Test 'canary list' parses correctly."""
        args = cli_parser.parse_args(['canary', 'list'])
        assert args.resource == 'canary'
        assert args.action == 'list'
        assert hasattr(args, 'func')

    @pytest.mark.unit
    def test_canary_create_parses(self, cli_parser):
        """Test 'canary create' parses with required args."""
        args = cli_parser.parse_args([
            'canary', 'create', 'my-canary', 'AWS_IAM_USER',
            '--env', 'abc-123', '--logging-id', 'def-456'
        ])
        assert args.resource == 'canary'
        assert args.action == 'create'
        assert args.name == 'my-canary'
        assert args.type == 'AWS_IAM_USER'
        assert args.env == 'abc-123'
        assert args.logging_id == 'def-456'

    @pytest.mark.unit
    def test_canary_create_with_optional_params(self, cli_parser):
        """Test 'canary create' with optional interval and params."""
        args = cli_parser.parse_args([
            'canary', 'create', 'test', 'GCP_BUCKET',
            '--env', 'e1', '--logging-id', 'l1',
            '--interval', '3600', '--params', '{"foo": "bar"}'
        ])
        assert args.interval == 3600
        assert args.params == '{"foo": "bar"}'

    @pytest.mark.unit
    def test_canary_delete_parses(self, cli_parser):
        """Test 'canary delete' parses correctly."""
        args = cli_parser.parse_args(['canary', 'delete', 'my-canary'])
        assert args.action == 'delete'
        assert args.name_or_id == 'my-canary'

    @pytest.mark.unit
    def test_canary_creds_parses(self, cli_parser):
        """Test 'canary creds' parses correctly."""
        args = cli_parser.parse_args(['canary', 'creds', 'my-canary'])
        assert args.action == 'creds'
        assert args.name == 'my-canary'

    @pytest.mark.unit
    def test_canary_trigger_parses(self, cli_parser):
        """Test 'canary trigger' parses correctly."""
        args = cli_parser.parse_args(['canary', 'trigger', 'my-canary'])
        assert args.action == 'trigger'
        assert args.name_or_id == 'my-canary'

    # ========== Environment Commands ==========
    
    @pytest.mark.unit
    def test_env_list_parses(self, cli_parser):
        """Test 'env list' parses correctly."""
        args = cli_parser.parse_args(['env', 'list'])
        assert args.resource == 'env'
        assert args.action == 'list'

    @pytest.mark.unit
    def test_env_create_parses(self, cli_parser):
        """Test 'env create' parses with required args."""
        args = cli_parser.parse_args([
            'env', 'create', 'prod', 'AWS',
            '--credentials', '{"key": "value"}'
        ])
        assert args.action == 'create'
        assert args.name == 'prod'
        assert args.provider == 'AWS'
        assert args.credentials == '{"key": "value"}'

    @pytest.mark.unit
    def test_env_sync_parses(self, cli_parser):
        """Test 'env sync' parses correctly."""
        args = cli_parser.parse_args(['env', 'sync'])
        assert args.action == 'sync'
        assert args.dry_run is False
        assert args.force is False
        assert args.validate is False

    @pytest.mark.unit
    def test_env_sync_with_flags(self, cli_parser):
        """Test 'env sync' with optional flags."""
        args = cli_parser.parse_args(['env', 'sync', '--dry-run', '--validate'])
        assert args.dry_run is True
        assert args.validate is True

    # ========== Logs Commands ==========
    
    @pytest.mark.unit
    def test_logs_list_parses(self, cli_parser):
        """Test 'logs list' parses correctly."""
        args = cli_parser.parse_args(['logs', 'list'])
        assert args.resource == 'logs'
        assert args.action == 'list'

    @pytest.mark.unit
    def test_logs_create_parses(self, cli_parser):
        """Test 'logs create' parses with required args."""
        args = cli_parser.parse_args([
            'logs', 'create', 'my-trail', 'AWS_CLOUDTRAIL',
            '--env', 'abc-123'
        ])
        assert args.action == 'create'
        assert args.name == 'my-trail'
        assert args.type == 'AWS_CLOUDTRAIL'
        assert args.env == 'abc-123'

    @pytest.mark.unit
    def test_logs_scan_parses(self, cli_parser):
        """Test 'logs scan' parses correctly."""
        args = cli_parser.parse_args(['logs', 'scan', '--env', 'abc-123'])
        assert args.action == 'scan'
        assert args.env == 'abc-123'

    # ========== Alerts Commands ==========
    
    @pytest.mark.unit
    def test_alerts_list_parses(self, cli_parser):
        """Test 'alerts list' parses correctly."""
        args = cli_parser.parse_args(['alerts', 'list'])
        assert args.resource == 'alerts'
        assert args.action == 'list'

    @pytest.mark.unit
    def test_alerts_list_with_filters(self, cli_parser):
        """Test 'alerts list' with filter options."""
        args = cli_parser.parse_args([
            'alerts', 'list', '--canary', 'my-canary', '--env', 'prod'
        ])
        assert args.canary == 'my-canary'
        assert args.env == 'prod'

    # ========== Resource Group Structure ==========
    
    @pytest.mark.unit
    def test_resource_groups_exist(self, cli_parser):
        """Test all expected resource groups are registered."""
        # Parse with just the resource to check it exists
        args = cli_parser.parse_args(['canary'])
        assert args.resource == 'canary'
        
        args = cli_parser.parse_args(['env'])
        assert args.resource == 'env'
        
        args = cli_parser.parse_args(['logs'])
        assert args.resource == 'logs'
        
        args = cli_parser.parse_args(['alerts'])
        assert args.resource == 'alerts'
