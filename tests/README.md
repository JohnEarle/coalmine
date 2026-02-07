# Tests

## Structure

```
tests/
├── conftest.py        # Shared fixtures (isolated_db, make_credential, etc.)
├── unit/              # Fast, no external dependencies
├── integration/       # Require database (uses in-memory SQLite)
└── e2e/               # End-to-end workflow tests
```

## Running Tests

All tests run inside Docker:

```bash
# All tests
docker compose run --rm app pytest -v

# Unit tests only (fast)
docker compose run --rm app pytest tests/unit/ -v

# Integration tests
docker compose run --rm app pytest tests/integration/ -v

# Single file
docker compose run --rm app pytest tests/unit/test_account_service.py -v
```

## Key Fixtures (`conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `isolated_db` | function | Fresh in-memory SQLite session per test |
| `make_credential` | function | Factory to create a `Credential` with defaults |
| `make_account` | function | Factory to create an `Account` linked to a credential |
| `mock_tofu` | function | Patches `TofuManager` for tests that don't need real infra |
