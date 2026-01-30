#!/bin/bash
# ops/startup.sh - Manage Forge Communicator service (start|stop|restart)
set -e

# Load environment variables from .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# --- CONFIG ---
VENV_DIR="$(dirname "$0")/../.venv"
REQUIREMENTS="$(dirname "$0")/../requirements.txt"
DB_CONTAINER="forge-db"
DB_PORT=5432

# --- FUNCTIONS ---
function ensure_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating virtualenv..."
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
}

function install_requirements() {
    echo "Installing/updating requirements..."
    pip install --upgrade pip
    pip install -r "$REQUIREMENTS"
}

function start_db() {
    if ! docker ps --format '{{.Names}}' | grep -q "^$DB_CONTAINER$"; then
        if docker ps -a --format '{{.Names}}' | grep -q "^$DB_CONTAINER$"; then
            echo "Removing old stopped DB container..."
            docker rm "$DB_CONTAINER"
        fi
        echo "Starting local PostgreSQL container ($DB_CONTAINER)..."
        docker run -d --name "$DB_CONTAINER" \
          -e POSTGRES_USER=forge \
          -e POSTGRES_PASSWORD=forge \
          -e POSTGRES_DB=forge_communicator \
          -p $DB_PORT:5432 postgres:14
    else
        echo "PostgreSQL container ($DB_CONTAINER) already running."
    fi
}

function stop_db() {
    if docker ps --format '{{.Names}}' | grep -q "^$DB_CONTAINER$"; then
        echo "Stopping PostgreSQL container ($DB_CONTAINER)..."
        docker stop "$DB_CONTAINER"
    else
        echo "No running PostgreSQL container ($DB_CONTAINER) found."
    fi
}

function run_migrations() {
    if command -v alembic >/dev/null 2>&1; then
        alembic upgrade head
    fi
}

function start_service() {
    ensure_venv
    install_requirements
    start_db
    run_migrations
    echo "Starting Forge Communicator... (logging to app.log)"
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" >> app.log 2>&1
}

function stop_service() {
    echo "Stopping Forge Communicator (uvicorn)..."
    pkill -f "uvicorn app.main:app" || echo "No running uvicorn process found."
    stop_db
}

function restart_service() {
    stop_service
    start_service
}

# --- MAIN ---
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac
