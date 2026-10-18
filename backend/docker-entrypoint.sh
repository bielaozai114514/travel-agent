
#!/bin/sh

set -e

echo "=========================================="
echo "TravelAgent Backend Docker Entrypoint"
echo "=========================================="

echo ""
echo "Initializing database..."

# Run Alembic migrations
echo "Running Alembic migrations..."
alembic upgrade head || echo "Alembic migrations failed (might be first run, continuing)"

# Initialize permissions
echo "Initializing permissions..."
python utils/init_permissions.py || echo "Permissions might already exist"

# Initialize admin user
echo "Initializing admin user..."
python utils/init_admin.py || echo "Admin might already exist"

echo ""
echo "Database initialization complete!"
echo ""
echo "Starting TravelAgent Backend..."
echo "=========================================="

exec "$@"

