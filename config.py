import os
import re
from typing import Optional, List

def _parse_aws_region(region_str: str) -> str:
    """Parse AWS region from environment variable that may contain descriptive text"""
    if not region_str:
        return "us-west-2"
    
    # If it's already a clean region code, return it
    if re.match(r'^[a-z]{2}-[a-z]+-\d+$', region_str):
        return region_str
    
    # Extract region code from descriptive text like "US East (Ohio) us-east-2"
    match = re.search(r'([a-z]{2}-[a-z]+-\d+)', region_str)
    if match:
        return match.group(1)
    
    # Fallback to default region
    return "us-west-2"

class Settings:
    """Application configuration settings"""
    
    # Supabase configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    # OpenAI configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    
    # AWS configuration
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = _parse_aws_region(os.getenv("AWS_REGION", "us-west-2"))
    S3_BUCKET: str = os.getenv("S3_BUCKET", "")
    
    # Processing configuration
    MAX_CHUNK_TOKENS: int = 800
    CHUNK_OVERLAP_TOKENS: int = 100
    MAX_PDF_SIZE_MB: int = 50
    MAX_TOKENS_PER_CHUNK: int = 1000
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Search configuration
    DEFAULT_SEARCH_RESULTS: int = 8
    MAX_SEARCH_RESULTS: int = 50
    
    def validate(self) -> List[str]:
        """Validate required settings and return any missing ones"""
        missing = []
        
        if not self.SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not self.SUPABASE_SERVICE_ROLE_KEY:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if not self.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not self.AWS_ACCESS_KEY_ID:
            missing.append("AWS_ACCESS_KEY_ID")
        if not self.AWS_SECRET_ACCESS_KEY:
            missing.append("AWS_SECRET_ACCESS_KEY")
        if not self.S3_BUCKET:
            missing.append("S3_BUCKET")
            
        return missing

# Global settings instance
settings = Settings()

# Validate settings on import
missing_settings = settings.validate()
if missing_settings:
    print(f"Warning: Missing required environment variables: {', '.join(missing_settings)}")
