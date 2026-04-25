# Image-Based Product Search System

A complete monolithic Python Flask application for uploading product images and searching for similar products using FAISS vector similarity search.

## 🎯 Features

- **Multi-angle Product Uploads**: Upload images from multiple angles (front, back, left, right, etc.)
- **Vector Search**: Fast similarity search using FAISS (Facebook AI Similarity Search)
- **Smart Aggregation**: Voting-based result aggregation across multiple product views
- **PostgreSQL Storage**: Persistent metadata storage with psycopg2
- **Responsive UI**: Modern HTML/CSS/JavaScript frontend with drag-and-drop
- **RESTful API**: JSON API endpoints for programmatic access
- **Production Ready**: Modular code, proper error handling, and logging

## 🏗️ Project Structure

```
project/
├── app.py                 # Main Flask application
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
├── README.md              # This file
│
├── templates/             # HTML templates
│   ├── index.html         # Home page
│   ├── upload.html        # Upload page
│   ├── search.html        # Search page
│   └── error.html         # Error page
│
├── static/                # Static files
│   ├── css/
│   │   └── style.css      # Styling
│   └── js/
│       └── main.js        # JavaScript
│
├── uploads/               # Uploaded images storage
│
├── embeddings/            # FAISS index storage
│   └── index.faiss        # FAISS vector index
│
├── services/              # Business logic
│   ├── __init__.py
│   ├── embedding.py       # Image embedding generation
│   ├── search.py          # FAISS search service
│   └── storage.py         # File storage management
│
├── models/                # Database layer
│   ├── __init__.py
│   └── db.py              # PostgreSQL operations
│
└── utils/                 # Utilities
    ├── __init__.py
    └── helpers.py         # Helper functions
```

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- pip (Python package manager)

### Step 1: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Setup PostgreSQL Database

```bash
# Create database
createdb image_search

# Or using psql:
psql -U postgres
CREATE DATABASE image_search;
```

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
# Set DB_HOST, DB_USER, DB_PASSWORD, etc.
```

### Step 4: Run Application

```bash
python app.py
```

The application will start at `http://localhost:5000`

## 📚 Usage

### 1. Upload Product Images

**Endpoint**: `POST /upload`

**Steps**:
1. Go to http://localhost:5000/upload
2. Enter Product ID (e.g., "PROD-001")
3. Select Image Angle (front, back, left, right, etc.)
4. Upload image file (JPEG, PNG, GIF, max 10MB)
5. Click "Upload Image"

**Process**:
- Image is saved to `uploads/{item_id}/{angle}.jpg`
- Metadata is stored in PostgreSQL `items_images` table
- Embedding vector is generated (512 dimensions)
- Vector is added to FAISS index
- Embedding metadata is stored in PostgreSQL `embeddings` table
- FAISS index is persisted to disk

### 2. Search Similar Products

**Endpoint**: `POST /search`

**Steps**:
1. Go to http://localhost:5000/search
2. Upload a query image
3. System searches for similar products

**Process**:
- Query image embedding is generated
- FAISS searches for top-5 similar vectors
- Results are aggregated by product ID (voting)
- Results ranked by similarity score (0-100%)
- Similar products displayed with match scores

### 3. API Endpoints

#### Get All Items
```bash
curl http://localhost:5000/api/items
```

#### Get Item Details
```bash
curl http://localhost:5000/api/item/{item_id}
```

#### Get System Statistics
```bash
curl http://localhost:5000/api/stats
```

## 🗄️ Database Schema

### items_images Table
```sql
CREATE TABLE items_images (
    id SERIAL PRIMARY KEY,
    item_id VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    angle VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### embeddings Table
```sql
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    image_id INT REFERENCES items_images(id) ON DELETE CASCADE,
    item_id VARCHAR(255) NOT NULL,
    faiss_index INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🧠 How Embeddings Work

The embedding process:

1. **Image Loading**: Load image and convert to RGB if needed
2. **Resizing**: Resize to 224x224 pixels
3. **Normalization**: Convert to numpy array and normalize to [0, 1]
4. **Flattening**: Flatten image to 1D vector (150,528 dimensions)
5. **Dimension Reduction**: Take first 512 dimensions (or pad with random noise)
6. **L2 Normalization**: Normalize embedding vector using L2 norm

Result: 512-dimensional feature vector representing the image

## 🔍 Search Algorithm

1. **Query Processing**: Generate embedding for query image
2. **FAISS Search**: Find top-k (default 5) nearest neighbors in FAISS index
3. **Mapping**: Convert FAISS indices back to product IDs using database
4. **Voting**: Aggregate results by product ID
5. **Ranking**: Sort by vote count and minimum distance
6. **Scoring**: Convert L2 distance to similarity score (0-100%)

Color-coded results:
- 🟢 **Green (80-100%)**: Very similar - likely same/very similar product
- 🟡 **Yellow (60-79%)**: Similar - likely same category
- 🟠 **Orange (0-59%)**: Low similarity - different products

## 📊 Configuration

Edit `config.py` to customize:

```python
# Image settings
IMAGE_SIZE = (224, 224)           # Resize dimensions
EMBEDDING_VECTOR_SIZE = 512       # Embedding dimension

# Search settings
SEARCH_TOP_K = 5                  # Number of results per search

# File settings
MAX_FILE_SIZE = 10 * 1024 * 1024 # 10MB
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}

# Database settings
DATABASE_URL = "postgresql://user:password@host:port/dbname"
```

## 🚀 Production Deployment

### Database Backup
```bash
pg_dump image_search > backup.sql
```

### FAISS Index Backup
```bash
cp embeddings/index.faiss embeddings/index.faiss.backup
```

### Environment Variables
Set these in production:
```bash
FLASK_ENV=production
DEBUG=False
SECRET_KEY=<generate-secure-key>
DB_HOST=<production-db-host>
DB_USER=<production-db-user>
DB_PASSWORD=<secure-password>
```

### Deployment Options

1. **Gunicorn + Nginx**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:8000 app:app
   ```

2. **Docker**
   ```dockerfile
   FROM python:3.9
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   CMD ["python", "app.py"]
   ```

3. **PythonAnywhere / Heroku**
   Follow platform-specific deployment guides

## ⚠️ Important Notes

1. **FAISS Index**: Persisted to disk automatically. Keep `embeddings/index.faiss` safe
2. **Database**: Ensure PostgreSQL is running before starting the app
3. **File Storage**: Images stored in `uploads/` directory. Ensure sufficient disk space
4. **Embedding Consistency**: Use same embedding function for upload and search
5. **Performance**: FAISS is optimized for CPUs. For large-scale deployment, consider GPU support

## 🐛 Troubleshooting

### PostgreSQL Connection Error
```
✗ Database connection failed
```
**Solution**: 
- Ensure PostgreSQL is running
- Check `.env` database credentials
- Verify database exists: `psql -l`

### FAISS Index Error
```
✗ Error creating FAISS index
```
**Solution**:
- Delete corrupted `embeddings/index.faiss`
- Restart application
- Re-upload images

### Image Upload Error
```
✗ Error saving image
```
**Solution**:
- Check disk space
- Verify `uploads/` directory permissions
- Check file size (max 10MB)

## 📖 API Examples

### Upload via API
```bash
curl -X POST http://localhost:5000/upload \
  -F "item_id=PROD-001" \
  -F "angle=front" \
  -F "image=@/path/to/image.jpg"
```

### Search via API
```bash
curl -X POST http://localhost:5000/search \
  -F "query_image=@/path/to/query.jpg"
```

### Get Statistics
```bash
curl http://localhost:5000/api/stats
```

Response:
```json
{
  "success": true,
  "data": {
    "total_items": 42,
    "total_images": 156,
    "total_embeddings": 156,
    "storage_mb": 234.5
  }
}
```

## 🔧 Development

### Debug Mode
Set `DEBUG=True` in `.env` for detailed error messages and auto-reload

### Database Inspection
```bash
# Connect to database
psql -d image_search

# List tables
\dt

# View images
SELECT * FROM items_images LIMIT 10;

# View embeddings
SELECT * FROM embeddings LIMIT 10;
```

### FAISS Index Info
```python
import faiss
index = faiss.read_index('embeddings/index.faiss')
print(f"Number of vectors: {index.ntotal}")
print(f"Vector dimension: {index.d}")
```

## 📝 Logging

The application logs to console. For file logging, modify `app.py`:

```python
import logging

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

## 🤝 Contributing

To extend the system:

1. **Custom Embedding Model**: Modify `services/embedding.py`
2. **Different Search Algorithm**: Extend `services/search.py` with other FAISS indices
3. **API Extensions**: Add routes to `app.py`
4. **Frontend Improvements**: Update `templates/` and `static/`

## 📄 License

MIT License

## 🙋 Support

For issues or questions:
1. Check the Troubleshooting section
2. Review logs in console output
3. Inspect database with psql
4. Check FAISS index status

## 🎓 Learning Resources

- **FAISS**: https://github.com/facebookresearch/faiss
- **Flask**: https://flask.palletsprojects.com/
- **PostgreSQL**: https://www.postgresql.org/docs/
- **Vector Search**: https://www.pinecone.io/learn/vector-search/

---

Built with ❤️ for image-based product search | Python + Flask + FAISS + PostgreSQL
# image-recognition
