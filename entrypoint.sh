#!/bin/sh
set -e

# Parse DATABASE_URL for pg_isready if available, otherwise use individual vars
if [ -n "$DATABASE_URL" ]; then
    # Extract host and port from DATABASE_URL
    # Format: postgresql://user:pass@host:port/dbname
    DB_HOST=$(echo $DATABASE_URL | sed -e 's/.*@//' -e 's/:.*//' -e 's/\/.*//')
    DB_PORT=$(echo $DATABASE_URL | sed -e 's/.*@//' -e 's/.*://' -e 's/\/.*//')
    # Default to 5432 if port extraction failed
    if [ "$DB_PORT" = "$DB_HOST" ]; then
        DB_PORT=5432
    fi
    echo "Using DATABASE_URL: connecting to $DB_HOST:$DB_PORT"
else
    DB_HOST=${DB_HOST:-db}
    DB_PORT=${DB_PORT:-5432}
    echo "Using DB_HOST=$DB_HOST DB_PORT=$DB_PORT"
fi

# Wait for database to be ready (max 60 seconds)
echo "Waiting for database at $DB_HOST:$DB_PORT..."
MAX_RETRIES=60
RETRY_COUNT=0
while ! nc -z $DB_HOST $DB_PORT 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Database not available after $MAX_RETRIES seconds"
        exit 1
    fi
    echo "Waiting for database... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 1
done
echo "Database is ready!"

# Run migrations
echo "Running database migrations..."
if alembic upgrade head; then
    echo "Migrations completed successfully"
else
    echo "WARNING: Migration failed, but continuing startup..."
    echo "You may need to run migrations manually"
fi

# Start the server
echo "Starting Forge Communicator..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
