"""
Stability tests for detection strategies.

Tests the core detection logic of CloudWatchLogsQuery, CloudTrailLookup,
and GcpAuditLogQuery without requiring real cloud services.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock
from types import SimpleNamespace

from src.monitors.strategies import (
    CloudWatchLogsQuery,
    CloudTrailLookup,
    GcpAuditLogQuery,
)
from src.monitors.base import Alert
from src.models import ResourceType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_resource(name="test-canary", phys_id="canary-bucket-xyz",
                   resource_type=ResourceType.AWS_BUCKET,
                   logging_resource=None, module_params=None):
    """Create a mock CanaryResource."""
    r = MagicMock()
    r.name = name
    r.current_resource_id = phys_id
    r.resource_type = resource_type
    r.logging_resource = logging_resource
    r.module_params = module_params
    return r


def _make_logging_resource(trail_name=None, log_group_name=None, name="trail-01"):
    lr = MagicMock()
    lr.name = name
    config = {}
    if trail_name:
        config["trail_name"] = trail_name
    if log_group_name:
        config["log_group_name"] = log_group_name
    lr.configuration = config or None
    return lr


START = datetime(2025, 1, 1)
END = datetime(2025, 1, 2)


# ===========================================================================
# CloudWatchLogsQuery
# ===========================================================================

class TestCloudWatchLogsQuery:
    """Tests for CloudWatchLogsQuery.detect()."""

    def test_log_group_from_linked_trail_name(self):
        """Tier 1: Prefers logging_resource.configuration.trail_name."""
        lr = _make_logging_resource(trail_name="my-trail")
        resource = _make_resource(logging_resource=lr)

        client = MagicMock()
        client.filter_log_events.return_value = {"events": []}

        strategy = CloudWatchLogsQuery(filter_pattern='{ $.eventName = "GetObject" }')
        strategy.detect(client, resource, START, END)

        call_kwargs = client.filter_log_events.call_args[1]
        assert call_kwargs["logGroupName"] == "/aws/cloudtrail/my-trail"

    def test_log_group_from_linked_log_group_name(self):
        """Tier 1b: Prefers explicit log_group_name over trail_name."""
        lr = _make_logging_resource(log_group_name="/custom/log-group")
        resource = _make_resource(logging_resource=lr)

        client = MagicMock()
        client.filter_log_events.return_value = {"events": []}

        strategy = CloudWatchLogsQuery(filter_pattern="filter")
        strategy.detect(client, resource, START, END)

        call_kwargs = client.filter_log_events.call_args[1]
        assert call_kwargs["logGroupName"] == "/custom/log-group"

    def test_log_group_from_params_fallback(self):
        """Tier 2: Falls back to module_params.ct_id."""
        resource = _make_resource(module_params={"ct_id": "param-trail"})

        client = MagicMock()
        client.filter_log_events.return_value = {"events": []}

        strategy = CloudWatchLogsQuery(filter_pattern="filter")
        strategy.detect(client, resource, START, END)

        call_kwargs = client.filter_log_events.call_args[1]
        assert call_kwargs["logGroupName"] == "/aws/cloudtrail/param-trail"

    def test_log_group_default(self):
        """Tier 3: Default fallback constructs from physical name."""
        resource = _make_resource(phys_id="my-bucket")

        client = MagicMock()
        client.filter_log_events.return_value = {"events": []}

        strategy = CloudWatchLogsQuery(filter_pattern="filter")
        strategy.detect(client, resource, START, END)

        call_kwargs = client.filter_log_events.call_args[1]
        assert call_kwargs["logGroupName"] == "/aws/cloudtrail/canary/my-bucket"

    def test_filter_pattern_substitution(self):
        """Resource ID placeholder gets replaced in filter_pattern."""
        resource = _make_resource(phys_id="bucket-abc")

        client = MagicMock()
        client.filter_log_events.return_value = {"events": []}

        strategy = CloudWatchLogsQuery(filter_pattern='{{$.requestParameters.bucketName = "{resource_id}"}}')
        strategy.detect(client, resource, START, END)

        call_kwargs = client.filter_log_events.call_args[1]
        assert "bucket-abc" in call_kwargs["filterPattern"]
        assert "{resource_id}" not in call_kwargs["filterPattern"]

    def test_parses_log_events_into_alerts(self):
        """Events returned from CloudWatch are parsed into Alert objects."""
        resource = _make_resource()

        ct_event = json.dumps({
            "eventName": "GetObject",
            "sourceIPAddress": "10.0.0.1",
            "userAgent": "aws-cli/2.0",
        })
        client = MagicMock()
        client.filter_log_events.return_value = {
            "events": [{
                "eventId": "evt-1",
                "timestamp": int(START.timestamp() * 1000),
                "message": ct_event,
            }]
        }

        strategy = CloudWatchLogsQuery(filter_pattern="filter")
        alerts = strategy.detect(client, resource, START, END)

        assert len(alerts) == 1
        assert alerts[0].event_name == "GetObject"
        assert alerts[0].source_ip == "10.0.0.1"
        assert alerts[0].external_id == "evt-1"


# ===========================================================================
# CloudTrailLookup
# ===========================================================================

class TestCloudTrailLookup:
    """Tests for CloudTrailLookup.detect()."""

    def test_deduplication(self):
        """Same EventId from multiple lookup keys is only returned once."""
        resource = _make_resource()

        client = MagicMock()
        event = {
            "EventId": "dup-event",
            "EventName": "PutObject",
            "EventTime": START,
            "CloudTrailEvent": json.dumps({"sourceIPAddress": "1.2.3.4"}),
        }
        # Both lookup keys return the same event
        client.lookup_events.return_value = {"Events": [event]}

        strategy = CloudTrailLookup(
            lookup_attr_keys=["BucketName", "ResourceName"],
        )
        alerts = strategy.detect(client, resource, START, END)

        assert len(alerts) == 1, "Duplicate events must be deduplicated"

    def test_s3_arn_format(self):
        """S3 buckets use ARN format for ResourceName lookups."""
        resource = _make_resource(
            phys_id="my-s3-bucket",
            resource_type=ResourceType.AWS_BUCKET,
        )

        client = MagicMock()
        client.lookup_events.return_value = {"Events": []}

        strategy = CloudTrailLookup(lookup_attr_keys=["ResourceName"])
        strategy.detect(client, resource, START, END)

        call_kwargs = client.lookup_events.call_args[1]
        lookup_val = call_kwargs["LookupAttributes"][0]["AttributeValue"]
        assert lookup_val == "arn:aws:s3:::my-s3-bucket"

    def test_iam_no_arn_format(self):
        """IAM users use the physical name directly, not ARN."""
        resource = _make_resource(
            phys_id="canary-iam-user",
            resource_type=ResourceType.AWS_IAM_USER,
        )

        client = MagicMock()
        client.lookup_events.return_value = {"Events": []}

        strategy = CloudTrailLookup(lookup_attr_keys=["ResourceName"])
        strategy.detect(client, resource, START, END)

        call_kwargs = client.lookup_events.call_args[1]
        lookup_val = call_kwargs["LookupAttributes"][0]["AttributeValue"]
        assert lookup_val == "canary-iam-user"

    def test_event_name_filter(self):
        """Only events matching event_names whitelist are returned."""
        resource = _make_resource()

        client = MagicMock()
        client.lookup_events.return_value = {"Events": [
            {
                "EventId": "e1", "EventName": "GetObject", "EventTime": START,
                "CloudTrailEvent": json.dumps({}),
            },
            {
                "EventId": "e2", "EventName": "ListBuckets", "EventTime": START,
                "CloudTrailEvent": json.dumps({}),
            },
        ]}

        strategy = CloudTrailLookup(
            lookup_attr_keys=["BucketName"],
            event_names=["GetObject"],
        )
        alerts = strategy.detect(client, resource, START, END)

        assert len(alerts) == 1
        assert alerts[0].event_name == "GetObject"


# ===========================================================================
# GcpAuditLogQuery
# ===========================================================================

class TestGcpAuditLogQuery:
    """Tests for GcpAuditLogQuery.detect()."""

    def test_filter_template_formatting(self):
        """resource_id, start_time, end_time are substituted into the filter."""
        resource = _make_resource(phys_id="gcp-bucket-123")

        client = MagicMock()
        client.list_entries.return_value = iter([])  # empty

        template = 'resource.labels.bucket_name="{resource_id}" AND timestamp>="{start_time}" AND timestamp<="{end_time}"'
        strategy = GcpAuditLogQuery(filter_template=template)
        strategy.detect(client, resource, START, END)

        call_kwargs = client.list_entries.call_args[1]
        filter_str = call_kwargs["filter_"]
        assert "gcp-bucket-123" in filter_str
        assert "{resource_id}" not in filter_str
        assert "{start_time}" not in filter_str

    def test_parses_audit_entries(self):
        """GCP audit log entries are parsed into Alert objects."""
        resource = _make_resource(phys_id="gcp-sa-xyz")

        entry = MagicMock()
        entry.timestamp = START
        entry.insert_id = "gcp-entry-1"
        entry.payload = {
            "methodName": "google.iam.serviceAccounts.keys.create",
            "requestMetadata": {
                "callerIp": "8.8.8.8",
                "callerSuppliedUserAgent": "gcloud/400.0.0",
            },
            "authenticationInfo": {
                "principalEmail": "attacker@evil.com",
            },
        }

        client = MagicMock()
        client.list_entries.return_value = iter([entry])

        strategy = GcpAuditLogQuery(filter_template="{resource_id}")
        alerts = strategy.detect(client, resource, START, END)

        assert len(alerts) == 1
        assert alerts[0].event_name == "google.iam.serviceAccounts.keys.create"
        assert alerts[0].source_ip == "8.8.8.8"
        assert "attacker@evil.com" in alerts[0].user_agent

    def test_get_service_name(self):
        strategy = GcpAuditLogQuery(filter_template="test")
        assert strategy.get_service_name() == "gcp_audit"
