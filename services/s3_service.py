import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

class S3Service:
    """AWS S3 service for PDF operations"""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize S3 client"""
        try:
            if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
                logger.warning("AWS credentials not provided. S3 operations will fail.")
                self.client = None
                return
                
            self.client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            logger.info("S3 client initialized successfully")
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.client = None
    
    def validate_s3_key(self, s3_key: str) -> bool:
        """Validate S3 key for security (prevent path traversal)"""
        if not s3_key:
            return False
        
        # Check for path traversal attempts
        dangerous_patterns = ['../', '..\\', '../', '..\\']
        if any(pattern in s3_key for pattern in dangerous_patterns):
            return False
        
        # Ensure key doesn't start with / or contain double slashes
        if s3_key.startswith('/') or '//' in s3_key:
            return False
        
        # Check file extension
        if not s3_key.lower().endswith('.pdf'):
            return False
        
        return True
    
    async def download_pdf(self, s3_key: str) -> bytes:
        """Download PDF from S3 and return bytes"""
        if not self.client:
            raise ValueError("S3 service not configured. Please provide AWS credentials.")
            
        if not self.validate_s3_key(s3_key):
            raise ValueError(f"Invalid S3 key: {s3_key}")
        
        try:
            logger.info(f"Downloading PDF from S3: {s3_key}")
            
            # Check if object exists and get its size
            head_response = self.client.head_object(Bucket=settings.S3_BUCKET, Key=s3_key)
            file_size_mb = head_response['ContentLength'] / (1024 * 1024)
            
            if file_size_mb > settings.MAX_PDF_SIZE_MB:
                raise ValueError(f"PDF file too large: {file_size_mb:.1f}MB (max: {settings.MAX_PDF_SIZE_MB}MB)")
            
            # Download the file
            response = self.client.get_object(Bucket=settings.S3_BUCKET, Key=s3_key)
            pdf_bytes = response['Body'].read()
            
            logger.info(f"Successfully downloaded PDF: {s3_key} ({file_size_mb:.1f}MB)")
            return pdf_bytes
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise FileNotFoundError(f"PDF not found in S3: {s3_key}")
            elif error_code == 'NoSuchBucket':
                raise ValueError(f"S3 bucket not found: {settings.S3_BUCKET}")
            else:
                logger.error(f"S3 client error: {e}")
                raise
        except Exception as e:
            logger.error(f"Failed to download PDF from S3: {e}")
            raise
    
    def check_object_exists(self, s3_key: str) -> bool:
        """Check if object exists in S3"""
        if not self.client:
            raise ValueError("S3 service not configured. Please provide AWS credentials.")
        try:
            self.client.head_object(Bucket=settings.S3_BUCKET, Key=s3_key)
            return True
        except ClientError:
            return False

# Global S3 service instance
s3_service = S3Service()
