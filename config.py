import os
# Configuration settings
class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///schedulizer.db")
    # Fix for Heroku PostgreSQL URL format
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "jZ3j3PfG-23oKAbKKeLv-2vQvNeuFNu1gZs07MoexQY")

from app import db
db.create_all()
exit()


