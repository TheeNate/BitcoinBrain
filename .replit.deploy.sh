#!/bin/bash
# Deployment script for Cloud Run
# This script ensures proper setup for deployment

echo "Setting up deployment..."

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -e .

# Start the application with proper Cloud Run configuration
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-5000} --workers 1