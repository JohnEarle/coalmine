"""
Contract tests to enforce stability guarantees.

These tests verify that the core extension points and interfaces remain stable.
Breaking any of these tests indicates a potential breaking change.
"""
import pytest
from src.models import ResourceType, LoggingProviderType
from src.resources.registry import ResourceRegistry
from src.resources.base import ResourceManager


@pytest.mark.unit
class TestResourceHandlerContracts:
    """Tests ensuring all resource types have properly registered handlers."""

    def test_all_resource_types_have_handlers(self):
        """Every ResourceType enum must have a registered handler."""
        for rt in ResourceType:
            handler = ResourceRegistry.get_handler(rt)
            assert isinstance(handler, ResourceManager), \
                f"Handler for {rt} is not a ResourceManager instance"

    def test_all_logging_provider_types_have_handlers(self):
        """Logging provider types that require handlers must be registered."""
        # Only test types that should have handlers (not all do)
        required_handlers = [
            LoggingProviderType.AWS_CLOUDTRAIL,
            LoggingProviderType.GCP_AUDIT_SINK,
        ]
        for lt in required_handlers:
            handler = ResourceRegistry.get_handler(lt)
            assert isinstance(handler, ResourceManager), \
                f"Handler for {lt} is not a ResourceManager instance"


@pytest.mark.unit
class TestResourceManagerInterface:
    """Tests ensuring handlers implement the required interface."""

    def test_resource_handlers_implement_get_tform_vars(self):
        """Each resource handler must implement get_tform_vars method."""
        for rt in ResourceType:
            handler = ResourceRegistry.get_handler(rt)
            assert callable(getattr(handler, 'get_tform_vars', None)), \
                f"Handler for {rt} missing get_tform_vars method"

    def test_resource_handlers_can_call_get_tform_vars(self):
        """get_tform_vars should accept the documented signature."""
        for rt in ResourceType:
            handler = ResourceRegistry.get_handler(rt)
            # Verify method signature is compatible
            import inspect
            sig = inspect.signature(handler.get_tform_vars)
            params = list(sig.parameters.keys())
            assert 'physical_id' in params, \
                f"Handler for {rt} get_tform_vars missing physical_id param"
            assert 'env_config' in params, \
                f"Handler for {rt} get_tform_vars missing env_config param"
            assert 'module_params' in params, \
                f"Handler for {rt} get_tform_vars missing module_params param"

    def test_resource_handlers_have_enable_logging(self):
        """Each handler should have enable_logging method (may be no-op)."""
        for rt in ResourceType:
            handler = ResourceRegistry.get_handler(rt)
            assert hasattr(handler, 'enable_logging'), \
                f"Handler for {rt} missing enable_logging method"

    def test_resource_handlers_have_disable_logging(self):
        """Each handler should have disable_logging method (may be no-op)."""
        for rt in ResourceType:
            handler = ResourceRegistry.get_handler(rt)
            assert hasattr(handler, 'disable_logging'), \
                f"Handler for {rt} missing disable_logging method"


@pytest.mark.unit
class TestEnumStability:
    """Tests to detect breaking changes to core enums."""

    def test_resource_type_values_stable(self):
        """ResourceType enum should contain expected values."""
        expected = {'AWS_BUCKET', 'GCP_BUCKET', 'GCP_SERVICE_ACCOUNT', 'AWS_IAM_USER'}
        actual = {rt.value for rt in ResourceType}
        assert expected <= actual, \
            f"Missing expected ResourceType values: {expected - actual}"

    def test_logging_provider_type_values_stable(self):
        """LoggingProviderType enum should contain expected values."""
        expected = {'AWS_CLOUDTRAIL', 'GCP_AUDIT_LOG', 'GCP_AUDIT_SINK'}
        actual = {lt.value for lt in LoggingProviderType}
        assert expected <= actual, \
            f"Missing expected LoggingProviderType values: {expected - actual}"

    def test_resource_status_values_stable(self):
        """ResourceStatus enum should contain expected values."""
        from src.models import ResourceStatus
        expected = {'CREATING', 'ACTIVE', 'ROTATING', 'DELETING', 'DELETED', 'ERROR', 'DRIFT'}
        actual = {rs.value for rs in ResourceStatus}
        assert expected <= actual, \
            f"Missing expected ResourceStatus values: {expected - actual}"

    def test_action_type_values_stable(self):
        """ActionType enum should contain expected values."""
        from src.models import ActionType
        expected = {'CREATE', 'ROTATE', 'DELETE', 'ALERT'}
        actual = {at.value for at in ActionType}
        assert expected <= actual, \
            f"Missing expected ActionType values: {expected - actual}"

    def test_alert_status_values_stable(self):
        """AlertStatus enum should contain expected values."""
        from src.models import AlertStatus
        expected = {'NEW', 'ACKNOWLEDGED', 'RESOLVED'}
        actual = {als.value for als in AlertStatus}
        assert expected <= actual, \
            f"Missing expected AlertStatus values: {expected - actual}"
