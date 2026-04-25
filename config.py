import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory for project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# Flask Configuration
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
DEBUG = FLASK_ENV == 'development'
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'image_search')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')

# Database Connection String
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# File paths
UPLOAD_DIR = BASE_DIR / 'uploads'
EMBEDDING_DIR = BASE_DIR / 'embeddings'
EMBEDDINGS_INDEX_PATH = EMBEDDING_DIR / 'index.faiss'

# Ensure directories exist
UPLOAD_DIR.mkdir(exist_ok=True)
EMBEDDING_DIR.mkdir(exist_ok=True)

# Image settings
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
IMAGE_SIZE = (224, 224)

# Embedding settings
EMBEDDING_VECTOR_SIZE = 512

# Search settings
SEARCH_TOP_K = 5

# Flask upload settings
MAX_CONTENT_LENGTH = MAX_FILE_SIZE

# Inventree API Configuration
INVENTREE_URL = os.getenv('INVENTREE_URL', 'https://mirorim.ddns.net:8111/')
INVENTREE_USERNAME = os.getenv('INVENTREE_USERNAME', 'admin')
INVENTREE_PASSWORD = os.getenv('INVENTREE_PASSWORD', 'admin')

# Required image angles
REQUIRED_ANGLES = ['front', 'back', 'side', 'left', 'bottom', 'top']
