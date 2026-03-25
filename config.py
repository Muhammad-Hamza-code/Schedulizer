import os
# Configuration settings
class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///schedulizer.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "jZ3j3PfG-23oKAbKKeLv-2vQvNeuFNu1gZs07MoexQY")


