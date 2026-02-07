# Scripts

Utility scripts for development, debugging, and one-time migrations. These are **not** part of the application runtime.

## Migration Scripts (One-Time Use)

| Script | Purpose |
|--------|---------|
| `migrate.py` | General database schema migration |
| `migrate_accounts.py` | Migrated CloudEnvironment → Account model |
| `migrate_environments.py` | Migrated environment data to credentials |
| `migrate_enum.py` | Fixed enum types in PostgreSQL |
| `add_last_checked_column.py` | Added `last_checked` column to resources |

## Debug / Troubleshooting

| Script | Purpose |
|--------|---------|
| `debug_creds.py` | Inspect credential state in database |
| `debug_cw_query.py` | Test CloudWatch log queries |
| `debug_gcp_logs.py` | Test GCP audit log queries |
| `debug_gcp_sink_name.py` | Inspect GCP sink naming |
| `debug_log_res.py` | Inspect logging resource state |
| `debug_monitor_gcp.py` | Test GCP monitoring flow |
| `debug_s3_events.py` | Test S3 event detection |

## Operational

| Script | Purpose |
|--------|---------|
| `destroy_all.py` | Tear down all deployed resources |
| `delete_resource.py` | Delete a specific resource by ID |
| `check_status.py` | Check resource statuses in database |
| `verify_alert.py` | Verify alert pipeline is working |
| `seed_env.py` | Seed a test environment |

## Cloud-Specific

| Script | Purpose |
|--------|---------|
| `enable_gcp_audit_logs.py` | Enable GCP audit logging for a project |
| `configure_log_exclusion.py` | Configure GCP log exclusions |
| `update_gcp_sink.py` | Update a GCP audit sink |
| `trigger_gcp_canary.py` | Manually trigger a GCP canary |
| `list_aws_logs.py` | List AWS CloudTrail configurations |
| `check_gcp_id.py` | Verify GCP project ID |

## Testing

| Script | Purpose |
|--------|---------|
| `integration_test.py` | Manual integration test runner |
| `test_sink_update.py` | Test GCP sink update logic |
