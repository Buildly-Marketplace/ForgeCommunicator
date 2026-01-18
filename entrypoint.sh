#!/bin/sh
set -e

# Wait for database
echo "Waiting for database..."
while ! pg_isready -h ${DB_HOST:-db} -p ${DB_PORT:-5432} -U ${DB_USER:-forge} -q; do
    sleep 1
done

# Run migrations
echo "Running migrations..."
alembic upgrade head

# Start the server
echo "Starting Forge Communicator..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
