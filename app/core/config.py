# File: app/core/config.py
"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()