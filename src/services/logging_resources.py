"""
Logging Resource Service

Provides business logic for managing logging resources.
"""
from typing import Optional

from .base import BaseService, ServiceResult, ListResult
from src.models import LoggingResource, LoggingProviderType, Account, TaskLog, TaskStatus


class LoggingResourceService(BaseService):
    """
    Service for managing logging resources.
    
    Logging resources are CloudTrail, GCP Audit Sink, etc.
    """
    
    def create(
        self,
        name: str,
        provider_type: str,
        account_id: str,
        config: Optional[dict] = None
    ) -> ServiceResult[dict]:
        """
        Queue creation of a new logging resource.
        
        Logging resource creation is asynchronous via Celery task.
        
        Args:
            name: Display name for the logging resource
            provider_type: Type (AWS_CLOUDTRAIL, GCP_AUDIT_SINK)
            account_id: UUID or name of the account
            config: Optional configuration dictionary
            
        Returns:
            ServiceResult containing task queued status
        """
        from src.tasks import create_logging_resource as create_logging_task
        
        # Validate provider type
        try:
            LoggingProviderType(provider_type)
        except ValueError:
            valid_types = [t.value for t in LoggingProviderType]
            return ServiceResult.fail(
                f"Invalid provider_type. Valid types: {valid_types}"
            )
        
        # Validate account exists
        account = self._resolve_by_id_or_name(Account, account_id)
        if not account:
            return ServiceResult.fail(f"Account '{account_id}' not found")
        
        try:
            async_result = create_logging_task.delay(
                name=name,
                provider_type_str=provider_type,
                account_id_str=str(account.id),
                config=config
            )
            log = TaskLog(
                celery_task_id=async_result.id,
                task_name="create_logging_resource",
                source="user",
                status=TaskStatus.PENDING,
            )
            self.db.add(log)
            self.db.commit()
            return ServiceResult.ok({"status": "queued", "name": name, "task_id": async_result.id})
        except Exception as e:
            return ServiceResult.fail(f"Error queuing logging resource creation: {e}")
    
    def list(self) -> ListResult[LoggingResource]:
        """
        List all logging resources.
        
        Returns:
            ListResult containing all logging resources
        """
        resources = self.db.query(LoggingResource).all()
        return ListResult(items=resources, total=len(resources))
    
    def get(self, identifier: str) -> ServiceResult[LoggingResource]:
        """
        Get a specific logging resource by ID or name.
        
        Args:
            identifier: Logging resource UUID or name
            
        Returns:
            ServiceResult containing the LoggingResource or error
        """
        resource = self._resolve_by_id_or_name(LoggingResource, identifier)
        if not resource:
            return ServiceResult.fail(f"Logging resource '{identifier}' not found")
        return ServiceResult.ok(resource)
    
    def scan(self, account_id: str) -> ServiceResult[dict]:
        """
        Scan existing CloudTrails/LogGroups in an account.
        
        Args:
            account_id: UUID or name of the account
            
        Returns:
            ServiceResult containing scan results
        """
        import boto3
        
        account = self._resolve_by_id_or_name(Account, account_id)
        if not account:
            return ServiceResult.fail(f"Account '{account_id}' not found")
        
        cred = account.credential
        if not cred:
            return ServiceResult.fail(f"Account '{account_id}' has no credential")
        
        if cred.provider != "AWS":
            return ServiceResult.fail("Only AWS supported for logs scan currently")
        
        secrets = cred.secrets or {}
        region = secrets.get("region", "us-east-1")
        
        try:
            session = boto3.Session(
                aws_access_key_id=secrets.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=secrets.get("AWS_SECRET_ACCESS_KEY"),
                region_name=region
            )
            
            # Scan CloudTrails
            trails = []
            ct = session.client("cloudtrail")
            try:
                trail_list = ct.describe_trails().get("trailList", [])
                for t in trail_list:
                    trails.append({
                        "name": t["Name"],
                        "arn": t["TrailARN"],
                        "log_group_arn": t.get("CloudWatchLogsLogGroupArn", "N/A")
                    })
            except Exception as e:
                return ServiceResult.fail(f"Error scanning trails: {e}")
            
            # Scan Log Groups
            log_groups = []
            logs = session.client("logs")
            try:
                response = logs.describe_log_groups(limit=50)
                for lg in response.get("logGroups", []):
                    log_groups.append({
                        "name": lg["logGroupName"],
                        "arn": lg["arn"]
                    })
            except Exception as e:
                return ServiceResult.fail(f"Error scanning log groups: {e}")
            
            return ServiceResult.ok({
                "account": account.name,
                "region": region,
                "trails": trails,
                "log_groups": log_groups
            })
            
        except Exception as e:
            return ServiceResult.fail(f"Error scanning: {e}")
