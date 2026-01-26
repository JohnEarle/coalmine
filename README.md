![Coalmine Logo](images/coalmine.png)

> **Cloud Canary Token Management** - Deploy, monitor, and rotate deceptive credentials across AWS and GCP to detect unauthorized access.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

> [!WARNING]
> **Alpha Version** - Coalmine is in early development. Functionality and configuration are subject to change. Basic functionality is the current priority, and the application should **not be considered fully security tested** for production use.

## Status

| Functional | Development (Unstable) | To Do |
|------------|------------------------|-------|
| AWS IAM User Canaries | GCP Service Account Canaries | Azure Support |
| AWS S3 Bucket Canaries | GCP Bucket Canaries | Web UI Dashboard |
| CloudTrail Monitoring | GCP Audit Log Monitoring | API Authentication |
| Email Alerts | Automatic Rotation | Webhook Alerts |
| Multi-Environment Support | | Syslog Alerts |
| PostgreSQL State Backend | | SIEM Integration |

## Overview

Coalmine automatically deploys and monitors "canary tokens" - decoy credentials and resources that trigger alerts when accessed by attackers. It supports:

- **AWS**: IAM Users, S3 Buckets
- **GCP**: Service Accounts, Cloud Storage Buckets

## Features

- 🔐 **Multi-Cloud Support** - AWS and GCP from a single interface
- 🔄 **Automatic Rotation** - Credentials rotate on configurable intervals
- 📊 **Centralized Monitoring** - CloudTrail and GCP Audit Log integration
- 🚨 **Flexible Alerting** - Email (Working), Webhook(WIP), and Syslog(WIP) notifications
- 🏗️ **Infrastructure as Code** - OpenTofu-managed resources
- 🔧 **YAML Configuration** - Easy customization without code changes

## Quick Start

### Prerequisites

- Docker & Docker Compose
- AWS credentials (for AWS canaries)
- GCP credentials (for GCP canaries)

### 1. Clone & Configure

```bash
git clone https://github.com/yourorg/coalmine.git
cd coalmine
cp .env.example .env
# Edit .env with your configuration
```

### 2. Start Services

```bash
docker compose up -d
```

### 3. Create a Cloud Environment

```bash
# AWS Environment
docker compose exec app python src/cli.py create-env dev-aws AWS \
  --credentials '{"aws_access_key_id": "...", "aws_secret_access_key": "...", "region": "us-east-1"}'

# GCP Environment  
docker compose exec app python src/cli.py create-env prod-gcp GCP \
  --credentials '{"type": "service_account", ...}'
```

### 4. Deploy a Canary

```bash
# Create an AWS IAM User canary
docker compose exec app python src/cli.py create my-canary AWS_IAM_USER --env dev-aws

# Create a GCP Service Account canary
docker compose exec app python src/cli.py create gcp-canary GCP_SERVICE_ACCOUNT --env prod-gcp
```

### 5. Verify Detection

```bash
# Trigger a test alert
docker compose exec app python src/cli.py trigger my-canary

# Wait for monitoring cycle (~1 min) then check alerts
docker compose exec app python src/cli.py list-alerts
```

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   CLI/API    │────▶│    Celery    │────▶│   OpenTofu   │
└──────────────┘     │    Worker    │     │   Templates  │
                     └──────────────┘     └──────────────┘
                            │                    │
                     ┌──────▼──────┐      ┌──────▼──────┐
                     │  PostgreSQL │      │  AWS / GCP  │
                     │  (Inventory)│      │  (Resources)│
                     └─────────────┘      └─────────────┘
                            │
                     ┌──────▼──────┐
                     │ Celery Beat │──▶ Scheduled Monitoring
                     └─────────────┘    & Rotation
```

## Configuration

### Alert Outputs (`config/alert_outputs.yaml`)

```yaml
outputs:
  email_admin:
    type: "email"
    enabled: true
    smtp_host: "smtp.example.com"
    smtp_port: 587
    use_tls: true
    from_addr: "alerts@example.com"
    to_addrs: ["security@example.com"]
```

### Detection Rules (`config/detections.yaml`)

```yaml
detections:
  AWS_IAM_USER:
    strategy: "CloudTrailLookup"
    lookup_attributes: ["Username", "ResourceName"]
    event_names: ["CreateAccessKey", "ConsoleLogin"]
```

See [config/README.md](config/README.md) for full configuration options.

## CLI Reference

| Command | Description |
|---------|-------------|
| `create <name> <type>` | Create a new canary |
| `delete <name>` | Delete a canary |
| `list` | List all canaries |
| `list-alerts` | View security alerts |
| `trigger <name>` | Test canary detection |
| `create-env <name> <provider>` | Register cloud environment |
| `help` | Show all commands |

## Resource Types

| Type | Provider | Description |
|------|----------|-------------|
| `AWS_IAM_USER` | AWS | IAM user with access keys |
| `AWS_BUCKET` | AWS | S3 bucket with logging |
| `GCP_SERVICE_ACCOUNT` | GCP | Service account with keys |
| `GCP_BUCKET` | GCP | Cloud Storage bucket |

## Development

```bash
# Run tests
docker compose exec app pytest tests/

# View logs
docker compose logs -f worker

# Rebuild after code changes
docker compose build && docker compose up -d
```

## Security Considerations

- **Never commit credentials** - Use `.env` files or secrets managers
- **Rotate admin credentials** - The cloud credentials used to manage canaries
- **Network isolation** - Run Coalmine in a secure network segment
- **Principle of least privilege** - Canary credentials should have minimal permissions

## Roadmap

### Feature Priorities

- **Azure & Entra ID Support** - Extend canary token deployment to Microsoft Azure and Entra ID
- **CI/CD Pipeline Integration** - Inject canary tokens directly into CI/CD pipelines for supply chain security
- **REST API** - Programmatic access for integrating Coalmine with other security tools
- **Additional Canary Resource Types** - Database tables, secret vaults, and other high-value targets

## License

[Apache License 2.0](LICENSE) - See LICENSE file for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
