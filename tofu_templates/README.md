# OpenTofu Templates

Each subdirectory contains the Terraform/OpenTofu configuration for a specific resource type.

## Structure

```
tofu_templates/
├── aws_bucket/          # AWS S3 bucket canary
├── aws_central_trail/   # AWS CloudTrail logging
├── aws_iam_user/        # AWS IAM user canary
├── gcp_audit_sink/      # GCP audit log sink
├── gcp_bucket/          # GCP Cloud Storage canary
└── gcp_service_account/ # GCP service account canary
```

## Naming Convention

Directory names must match the `template` field in `config/resource_types.yaml`. For example:

```yaml
# config/resource_types.yaml
resource_types:
  AWS_BUCKET:
    template: aws_bucket  # → tofu_templates/aws_bucket/
```

## How Templates Are Used

1. `TofuManager` copies `.tf` files from the template directory to a per-resource working directory
2. `tofu init` is run with a PostgreSQL backend configuration
3. `tofu apply` is called with variables provided by the resource handler (`src/resources/`)

## Adding a New Template

1. Create a new directory: `tofu_templates/<name>/`
2. Add `main.tf` with resource definitions, `variables.tf` for inputs, `outputs.tf` for outputs
3. Register the template in `config/resource_types.yaml`
4. Implement a handler in `src/resources/` and register it in `src/resources/registry.py`
