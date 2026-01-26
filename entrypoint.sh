#!/bin/bash
set -e

# Run schema initialization
python -c "from src.models import init_db; init_db()"
echo "Database schema ensured."

# Execute the command passed to docker
exec "$@"
