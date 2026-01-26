# Coalmine - Configuration Guide

This directory contains YAML configuration files for easy management of canary types and detection strategies.

## Files

### `resource_types.yaml`
Defines all canary resource types supported by the system.

**To add a new resource type:**
1. Add an entry under `resource_types:`
2. Create the Tofu template in `tofu_templates/<template_name>/`
3. Add a detection in `detections.yaml`
4. Restart the worker

### `detections.yaml`
Defines how to detect access to each canary resource type.

**To modify detection patterns:**
1. Find the resource type entry
2. Modify the `filter_pattern` or `event_names`
3. Restart the worker

## Available Detection Strategies

| Strategy | Provider | Description |
|----------|----------|-------------|
| `CloudWatchLogsQuery` | AWS | Queries CloudWatch Logs using filter patterns |
| `CloudTrailLookup` | AWS | Uses CloudTrail LookupEvents API |
| `GcpAuditLogQuery` | GCP | Queries Cloud Logging with filter syntax |

## Examples

### Adding a new AWS resource type

```yaml
# resource_types.yaml
resource_types:
  AWS_SECRETS_MANAGER:
    description: "Secrets Manager secret for detecting unauthorized access"
    provider: AWS
    template: aws_secrets_manager
    requires_logging: false
```

```yaml
# detections.yaml
detections:
  AWS_SECRETS_MANAGER:
    strategy: CloudTrailLookup
    lookup_attributes:
      - ResourceName
    event_names:
      - GetSecretValue
      - DescribeSecret
```

Then create `tofu_templates/aws_secrets_manager/main.tf` with the resource definition.
