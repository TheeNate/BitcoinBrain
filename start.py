
#!/usr/bin/env python3
import os
import uvicorn

if __name__ == "__main__":
    # Use PORT environment variable for Cloud Run deployment, fallback to 5000
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        access_log=True,
        log_level="info"
    )
