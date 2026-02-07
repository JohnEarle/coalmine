#!/bin/bash
set -e

# Install/update dependencies (handles hot-reload dev environment)
pip install --quiet --disable-pip-version-check -r requirements.txt

# Run schema initialization
python -c "from src.models import init_db; init_db()"
echo "Database schema ensured."

# Execute the command passed to docker
exec "$@"
