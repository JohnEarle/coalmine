
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.monitors.aws_cloudtrail import AwsCloudTrailMonitor
from src.models import CanaryResource, ResourceType, CloudEnvironment

class TestCentralMonitoring(unittest.TestCase):
    def setUp(self):
        self.env = MagicMock(spec=CloudEnvironment)
        self.env.credentials = {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"}
        self.env.config = {"region": "us-east-1"}
        self.monitor = AwsCloudTrailMonitor(self.env)

    @patch("src.monitors.aws_cloudtrail.boto3.client")
    def test_check_bucket_with_central_trail(self, mock_boto):
        # Setup Mock Client
        mock_logs_client = MagicMock()
        mock_boto.return_value = mock_logs_client
        
        # Setup Resource using Central Trail via ct_id
        resource = MagicMock(spec=CanaryResource)
        resource.name = "deceptive-bucket"
        resource.resource_type = ResourceType.AWS_BUCKET
        resource.current_resource_id = "deceptive-bucket-physical"
        resource.module_params = {"ct_id": "central-trail-01"} # Trail Name
        
        start_time = datetime(2023, 1, 1, 10, 0, 0)
        end_time = datetime(2023, 1, 1, 10, 10, 0)
        
        # Call check
        self.monitor.check(resource, start_time, end_time)
        
        # Verify boto3 call used the correct Log Group
        # Expecting /aws/cloudtrail/central-trail-01
        expected_log_group = "/aws/cloudtrail/central-trail-01"
        
        mock_logs_client.filter_log_events.assert_called()
        call_args = mock_logs_client.filter_log_events.call_args[1]
        self.assertEqual(call_args["logGroupName"], expected_log_group)
        print("Verified Log Group Name: /aws/cloudtrail/central-trail-01")

    @patch("src.monitors.aws_cloudtrail.boto3.client")
    def test_check_bucket_with_explicit_log_group(self, mock_boto):
        # Setup Mock Client
        mock_logs_client = MagicMock()
        mock_boto.return_value = mock_logs_client
        
        # Setup Resource using direct Log Group path
        resource = MagicMock(spec=CanaryResource)
        resource.name = "custom-bucket"
        resource.resource_type = ResourceType.AWS_BUCKET
        resource.current_resource_id = "custom-bucket-physical"
        resource.module_params = {"ct_id": "/aws/cloudtrail/my-custom-group"} 
        
        start = datetime.now()
        end = datetime.now()
        
        self.monitor.check(resource, start, end)
        
        call_args = mock_logs_client.filter_log_events.call_args[1]
        self.assertEqual(call_args["logGroupName"], "/aws/cloudtrail/my-custom-group")
        print("Verified Explicit Log Group: /aws/cloudtrail/my-custom-group")

if __name__ == "__main__":
    unittest.main()
