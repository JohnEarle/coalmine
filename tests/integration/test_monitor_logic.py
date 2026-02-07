
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from src.monitors.aws_cloudtrail import AwsCloudTrailMonitor
from src.models import CanaryResource, ResourceType, Account
import json

def test_aws_bucket_monitoring_logic():
    # Setup
    cred = MagicMock()
    cred.provider = "AWS"
    cred.secrets = {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"}
    env = MagicMock(spec=Account)
    env.credential = cred
    env.account_id = "123456789012"

    resource = MagicMock(spec=CanaryResource)
    resource.resource_type = ResourceType.AWS_BUCKET
    resource.current_resource_id = "my-test-bucket"
    resource.name = "my-canary"
    
    monitor = AwsCloudTrailMonitor(env)
    
    # Mock Boto3 Client
    mock_client = MagicMock()
    monitor._get_client = MagicMock(return_value=mock_client)
    
    # Mock Log Response
    # CloudWatch Logs returns events with 'message' being the JSON string of the CloudTrail event
    start_time = datetime.utcnow() - timedelta(minutes=10)
    end_time = datetime.utcnow()
    
    cloudtrail_event_payload = {
        "eventVersion": "1.08",
        "eventTime": "2023-01-01T12:00:00Z",
        "eventSource": "s3.amazonaws.com",
        "eventName": "GetObject",
        "sourceIPAddress": "192.168.1.1",
        "userAgent": "Boto3/1.26.0",
        "requestParameters": {
            "bucketName": "my-test-bucket",
            "key": "secret.txt"
        }
    }
    
    mock_response = {
        "events": [
            {
                "logStreamName": "stream1",
                "timestamp": 1672574400000,
                "message": json.dumps(cloudtrail_event_payload),
                "ingestionTime": 1672574400000,
                "eventId": "event1"
            }
        ]
    }
    
    mock_client.filter_log_events.return_value = mock_response
    
    # Execute
    alerts = monitor.check(resource, start_time, end_time)
    
    # Verify Call
    log_group_name = "/aws/cloudtrail/canary/my-test-bucket"
    mock_client.filter_log_events.assert_called_once()
    call_kwargs = mock_client.filter_log_events.call_args[1]
    
    assert call_kwargs["logGroupName"] == log_group_name
    assert call_kwargs["filterPattern"] == '{ ($.eventName = "GetObject") || ($.eventName = "ListObjects") }'
    
    # Verify Parsing
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.event_name == "GetObject"
    assert alert.source_ip == "192.168.1.1"
    assert alert.resource_name == "my-test-bucket"

if __name__ == "__main__":
    test_aws_bucket_monitoring_logic()
    print("Test Passed: Logic Verified")
