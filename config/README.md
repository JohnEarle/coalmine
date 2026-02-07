# Configuration

YAML configuration files for Coalmine. Environment variables can be used with `${VAR_NAME}` syntax in any YAML value.

## Files

### `credentials.yaml`
Defines cloud credentials and their associated accounts. Sync with `coalmine credentials sync`.

**To add a credential:**
1. Add an entry under `credentials:` with `provider`, `auth_type`, `secrets`, and `accounts`
2. Run `coalmine credentials sync --dry-run` to preview
3. Run `coalmine credentials sync` to apply

### `resource_types.yaml`
Defines all canary resource types supported by the system.

**To add a new resource type:**
1. Add an entry under `resource_types:`
2. Create the Tofu template in `tofu_templates/<template_name>/`
3. Add a detection in `detections.yaml`
4. Restart the worker

### `detections.yaml`
Defines how to detect access to each canary resource type.

### `alert_outputs.yaml`
Configures notification channels (email, webhook, syslog).

### `api_keys.yaml`
Defines API keys for programmatic access. Keys support permissions, scopes, and IP allowlists.

### `auth.yaml`
Authentication configuration — JWT settings, session config, and optional OIDC provider.

### `rbac_model.conf` / `rbac_policy.csv`
Casbin RBAC model and policy definitions. Controls which roles can access which resources.

## Available Detection Strategies

| Strategy | Provider | Description |
|----------|----------|-------------|
| `CloudWatchLogsQuery` | AWS | Queries CloudWatch Logs using filter patterns |
| `CloudTrailLookup` | AWS | Uses CloudTrail LookupEvents API |
| `GcpAuditLogQuery` | GCP | Queries Cloud Logging with filter syntax |

## Example: Adding a New AWS Resource Type

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
