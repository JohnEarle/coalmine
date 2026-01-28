# Contributing to Coalmine

Thank you for your interest in contributing to Coalmine! This document provides guidelines for setting up your development environment, understanding the codebase, and submitting changes.

## Development Workflow

### Branching Strategy
We use a **Gitflow-inspired** workflow:
- **`main`**: Stable production releases. Do not commit directly here.
- **`development`**: The active integration branch. **Base your Feature Branches from here.**
- **`feature/*`**: Create a new branch for each feature or fix (e.g., `feature/add-azure-provider`, `fix/logging-race-condition`).

### Pull Requests
1. Fork the repo and clone it locally.
2. Checkout the `development` branch: `git checkout development`.
3. Create your feature branch: `git checkout -b feature/my-cool-feature`.
4. Make your changes and commit.
5. Push to your fork and submit a Pull Request to the `development` branch of the main repository.

## Component Overview

Coalmine is composed of several key modules working together in a Dockerized environment:

### 1. **Core Logic (`src/`)**
- **`cli.py`**: The entry point for all user interactions. Parses arguments and puts tasks onto the Celery queue.
- **`config_loader.py`**: Handles loading YAML configuration (`config/`) and securely expanding environment variables.
- **`tofu_manager.py`**: A wrapper around the OpenTofu (Terraform) binary. Handles `init`, `plan`, `apply`, and `destroy` commands and manages state file locations.

### 2. **Task Queue (`src/tasks/`)**
Heavy lifting is done asynchronously by Celery workers to ensure the CLI remains responsive.
- **`canary.py`**: The "Brain" of resource lifecycle. Handles creation, rotation, and deletion of canaries.
- **`monitoring.py`**: Polls cloud logs (CloudWatch/Stackdriver) for alertness.
- **`logging.py`**: Manages the setup of centralized logging infrastructure (CloudTrails, Audit Sinks).

### 3. **Resource Handlers (`src/resources/`)**
We use a **Registry Pattern** to support multi-cloud extensibility.
- **`registry.py`**: Maps `ResourceType` enums to specific handler classes.
- **`base.py`**: The abstract base class that all resource handlers must implement.
- **`aws_*.py` / `gcp_*.py`**: Provider-specific implementations that translate abstract params into Tofu variables.

### 4. **Database (`src/models.py`)**
A PostgreSQL database stores the inventory of active canaries, their current status, and audit history.
- **`CanaryResource`**: The main record for a deployed decoy.
- **`CloudEnvironment`**: Stores credentials and config for a specific cloud account.

## Working with OpenTofu Templates

All infrastructure logic resides in `tofu_templates/`.
- Each resource type has its own directory (e.g., `tofu_templates/aws_bucket/`).
- When adding a new resource type, you **must** create a corresponding template directory.
- Use `src/tofu_manager.py` for all interactions with tofu; avoid calling the binary directly in Python code.

## Running Tests

We use `pytest` for testing. Since the application is containerized, tests are best run inside the container to access the database and environment variables.

```bash
# Run all tests
docker compose exec app pytest tests/

# Run a specific test file
docker compose exec app pytest tests/test_logic.py
```

## Adding a New Resource Type

1.  **Define Type**: Add a new enum to `ResourceType` in `src/models.py` and `config/resource_types.yaml`.
2.  **Create Template**: Add a new directory in `tofu_templates/<new_type>/` with standard `main.tf`, `variables.tf`, and `outputs.tf`.
3.  **Implement Handler**: Create `src/resources/<new_type>.py` extending `ResourceManager`. Implement `get_tform_vars`.
4.  **Register**: Add your new handler to `src/resources/registry.py`.
5.  **Test**: Add a test case and verify creation/deletion.
