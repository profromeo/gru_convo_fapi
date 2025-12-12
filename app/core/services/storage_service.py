import logging
import json
import os
from typing import Optional, Dict, Any
from minio import Minio
from minio.error import S3Error
from app.config import Settings

from app.core.models.convo import MinioConfig

class StorageService:
    """Service for handling file storage operations using MinIO"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.client = None
        self.bucket_name = getattr(settings, 'minio_bucket_name', 'whatsapp-media')
        
        self._initialize_client()
        
    def _initialize_client(self):
        """Initialize MinIO client"""
        try:
            endpoint = getattr(self.settings, 'minio_endpoint', None)
            access_key = getattr(self.settings, 'minio_access_key', None)
            secret_key = getattr(self.settings, 'minio_secret_key', None)
            secure = getattr(self.settings, 'minio_secure', True)
            
            if endpoint and access_key and secret_key:
                self.client = Minio(
                    endpoint,
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=secure
                )
                self.logger.info("MinIO client initialized successfully")
            else:
                self.logger.warning("MinIO configuration missing. Storage service disabled.")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize MinIO client: {e}")

    def ensure_bucket_exists(self, bucket_name: str = None) -> bool:
        """Ensure the bucket exists and sets public policy"""
        if not self.client:
            return False
            
        target_bucket = bucket_name or self.bucket_name
        
        try:
            if not self.client.bucket_exists(target_bucket):
                self.client.make_bucket(target_bucket)
                self.logger.info(f"Created bucket: {target_bucket}")
                
                # Set public read policy
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                            "Resource": f"arn:aws:s3:::{target_bucket}",
                        },
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": "s3:GetObject",
                            "Resource": f"arn:aws:s3:::{target_bucket}/*",
                        },
                    ],
                }
                self.client.set_bucket_policy(target_bucket, json.dumps(policy))
                self.logger.info(f"Set public policy for bucket: {target_bucket}")
                
            return True
        except Exception as e:
            self.logger.error(f"Bucket error for {target_bucket}: {e}")
            return False

    def upload_file(self, file_path: str, object_name: str, content_type: str = None) -> Optional[str]:
        """Upload a file to MinIO and return its public URL"""
        if not self.client:
            self.logger.error("MinIO client not initialized")
            return None
            
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return None
            
        try:
            # Ensure bucket exists
            if not self.ensure_bucket_exists():
                return None
            
            # Upload file
            self.client.fput_object(
                self.bucket_name,
                object_name,
                file_path,
                content_type=content_type
            )
            
            self.logger.info(f"Uploaded {file_path} to {self.bucket_name}/{object_name}")
            
            # Construct public URL
            protocol = "https" if getattr(self.settings, 'minio_secure', True) else "http"
            endpoint = getattr(self.settings, 'minio_endpoint', 'localhost')
            url = f"{protocol}://{endpoint}/{self.bucket_name}/{object_name}"
            
            return url
            
        except Exception as e:
            self.logger.error(f"Upload error for {object_name}: {e}")
            return None

    def get_file_url(self, object_name: str, minio_config: Optional[MinioConfig] = None) -> str:
        """Get file URL from object name.
        
        Args:
           object_name: The MinIO object name
           minio_config: Optional custom MinIO configuration
           
        Returns:
            Public or presigned URL for the file
        """
        if not object_name:
            return ""
            
        # Check if it's already a full URL
        if object_name.startswith(("http://", "https://")):
            return object_name
            
        if minio_config:
            protocol = "https" if minio_config.secure else "http"
            endpoint = minio_config.endpoint
            bucket = minio_config.bucket_name
            return f"{protocol}://{endpoint}/{bucket}/{object_name}"
            
        # Construct public URL (assuming public bucket as per ensure_bucket_exists)
        protocol = "https" if getattr(self.settings, 'minio_secure', True) else "http"
        endpoint = getattr(self.settings, 'minio_endpoint', 'localhost')
        url = f"{protocol}://{endpoint}/{self.bucket_name}/{object_name}"
        
        return url

    def download_file(self, object_name: str, file_path: str, minio_config: Optional[MinioConfig] = None) -> bool:
        """Download a file from MinIO to local path.
        
        Args:
            object_name: The MinIO object name
            file_path: Local path to save the file
            minio_config: Optional custom MinIO configuration
            
        Returns:
            True if successful, False otherwise
        """
        client = self.client
        bucket = self.bucket_name
        
        if minio_config:
            try:
                client = Minio(
                    minio_config.endpoint,
                    access_key=minio_config.access_key,
                    secret_key=minio_config.secret_key,
                    secure=minio_config.secure
                )
                bucket = minio_config.bucket_name
            except Exception as e:
                self.logger.error(f"Failed to create temp MinIO client: {e}")
                return False
        
        if not client:
            self.logger.error("MinIO client not initialized")
            return False
            
        try:
            client.fget_object(bucket, object_name, file_path)
            self.logger.info(f"Downloaded {object_name} to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Download error for {object_name}: {e}")
            return False


