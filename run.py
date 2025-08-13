#!/usr/bin/env python3
"""
Entrypoint script for running the Bitcoin Knowledge Store API
Optimized for Cloud Run deployment with proper port configuration
"""
import os
import uvicorn

if __name__ == "__main__":
    # Use PORT environment variable for Cloud Run, fallback to 5000
    port = int(os.environ.get("PORT", 5000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
        access_log=True
    )