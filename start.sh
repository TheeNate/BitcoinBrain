#!/bin/bash
# Production start script for Cloud Run deployment
# This ensures proper port binding and health check compatibility

# Export PORT if not set (Cloud Run sets this)
export PORT=${PORT:-5000}

# Start the application
exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --access-log