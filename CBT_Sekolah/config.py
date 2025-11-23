import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'rahasia123')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///cbt.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False