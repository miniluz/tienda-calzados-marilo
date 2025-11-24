#!/bin/bash
set -e

echo "Starting Django application..."

if [ -z "$USE_SQLITE" ]; then
    echo "Waiting for PostgreSQL..."
    while ! pg_isready -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-postgres}" > /dev/null 2>&1; do
        sleep 1
    done
    echo "PostgreSQL is ready!"
fi

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Application setup complete!"

exec "$@"
