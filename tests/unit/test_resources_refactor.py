import pytest
from unittest.mock import MagicMock
from src.resources.base import ResourceManager
from src.resources.aws_bucket import AwsBucketHandler
from src.resources.aws_iam_user import AwsIamUserHandler
from src.resources.gcp_service_account import GcpServiceAccountHandler
from src.resources.gcp_bucket import GcpBucketHandler
from src.models import LoggingProviderType

class TestResourceManager:
    def test_resolve_env_config_aws(self):
        handler = AwsBucketHandler()
        account = MagicMock()
        account.credential.secrets = {"aws_region": "us-west-2"}
        account.account_id = "123456789012"

        env_config = handler.resolve_env_config(account)
        assert env_config["aws_region"] == "us-west-2"

    def test_resolve_env_config_gcp(self):
        handler = GcpBucketHandler()
        account = MagicMock()
        account.credential.secrets = {"project_id": "my-project"}

        env_config = handler.resolve_env_config(account)
        assert env_config["project_id"] == "my-project"

    def test_resolve_env_config_gcp_fallback_account_id(self):
        handler = GcpBucketHandler()
        account = MagicMock()
        account.credential.secrets = {}
        account.account_id = "fallback-project"

        env_config = handler.resolve_env_config(account)
        assert env_config["project_id"] == "fallback-project"

    def test_resolve_env_config_gcp_fallback_exec_env(self):
        handler = GcpBucketHandler()
        account = MagicMock()
        account.credential.secrets = {}
        account.account_id = None
        exec_env = {"GOOGLE_CLOUD_PROJECT": "env-project"}

        env_config = handler.resolve_env_config(account, exec_env)
        assert env_config["project_id"] == "env-project"

    def test_validate_aws_bucket_success(self):
        handler = AwsBucketHandler()
        account = MagicMock()
        account.credential.provider = "AWS"
        log_res = MagicMock()

        handler.validate(account, logging_resource=log_res)

    def test_validate_aws_bucket_fail_provider(self):
        handler = AwsBucketHandler()
        account = MagicMock()
        account.credential.provider = "GCP"
        log_res = MagicMock()

        with pytest.raises(ValueError, match="Account provider mismatch"):
            handler.validate(account, logging_resource=log_res)

    def test_validate_aws_bucket_fail_no_logging(self):
        handler = AwsBucketHandler()
        account = MagicMock()
        account.credential.provider = "AWS"

        with pytest.raises(ValueError, match="requires a valid logging_resource_id"):
            handler.validate(account, logging_resource=None)

    def test_validate_aws_iam_user_success(self):
        handler = AwsIamUserHandler()
        account = MagicMock()
        account.credential.provider = "AWS"

        handler.validate(account)

    def test_validate_gcp_service_account_success(self):
        handler = GcpServiceAccountHandler()
        account = MagicMock()
        account.credential.provider = "GCP"

        handler.validate(account)

    def test_validate_gcp_bucket_success(self):
        handler = GcpBucketHandler()
        account = MagicMock()
        account.credential.provider = "GCP"

        handler.validate(account)
