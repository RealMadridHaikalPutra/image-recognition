# 🗄️ Database Setup Guide

Your Flask app can now run with or without PostgreSQL! Choose your path below.

---

## ✅ Option 1: Run WITHOUT PostgreSQL (Recommended for Testing)

### What You Can Do
- ✅ Upload images with advanced CLIP embeddings
- ✅ Search for similar images
- ✅ Test all embedding features
- ❌ Database features (optional, can add later)

### How to Start
```bash
python app.py
```

You'll see this warning (it's fine):
```
⚠️  Database not available: connection to server at "localhost"...
   App will run in offline mode (embeddings only)
```

The app will start and you can use `/upload` and `/search` endpoints!

---

## 🔧 Option 2: Use PostgreSQL (For Production)

### Prerequisites
- PostgreSQL 12+ installed and running
- Correct credentials in `.env` file

### Step 1: Check Your .env File
File: `.env` (should exist in project root)

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=image-recognition
DB_USER=postgres
DB_PASSWORD=1234
```

### Step 2: Create Database
Run on PostgreSQL:
```sql
CREATE DATABASE "image-recognition";
```

### Step 3: Verify Password
Your PostgreSQL `postgres` user must have password `1234`.

To set it:
```sql
ALTER USER postgres WITH PASSWORD '1234';
```

### Step 4: Start App
```bash
python app.py
```

You should see:
```
✓ Connected to PostgreSQL
✓ Database tables initialized
```

---

## 🐛 Troubleshooting

### Error: "password authentication failed"
**Solution:** PostgreSQL password doesn't match `.env` file

**Fix:**
```sql
-- On PostgreSQL
ALTER USER postgres WITH PASSWORD '1234';
```

Or change `.env`:
```
DB_PASSWORD=your_postgres_password
```

### Error: "database 'image-recognition' does not exist"
**Solution:** Create the database

**Fix:**
```sql
-- On PostgreSQL
CREATE DATABASE "image-recognition";
```

### "localhost" vs "127.0.0.1"
If you get connection errors, try:

In `.env`, change:
```
DB_HOST=127.0.0.1
```

Instead of `localhost`

### PostgreSQL Not Running
**Windows:**
```bash
# Check if service is running
Get-Service postgresql-x64-*

# Start the service
Start-Service postgresql-x64-14  # adjust version
```

**macOS:**
```bash
brew services start postgresql
```

**Linux:**
```bash
sudo systemctl start postgresql
```

---

## 📊 Database Schema

When connected, the app automatically creates:

### `items_images` table
```
id (INT) - Primary key
item_id (VARCHAR) - Product ID
file_path (TEXT) - Image path
angle (VARCHAR) - Image angle
created_at (TIMESTAMP) - Upload time
```

### `embeddings` table
```
id (INT) - Primary key
image_id (INT) - FK to items_images
item_id (VARCHAR) - Product ID
faiss_index (INT) - FAISS vector index
created_at (TIMESTAMP) - Creation time
```

---

## 🔄 Switching Between Modes

### To Use PostgreSQL After Testing
1. Set up PostgreSQL as described above
2. Update `.env` with correct credentials
3. Restart app: `python app.py`

### To Go Back to Offline Mode
Just use a wrong password or shutdown PostgreSQL. App will continue working offline.

---

## ✨ Testing Without Database

The advanced embedding system works perfectly without PostgreSQL:

```python
# This works offline
from services.advanced_embedding import AdvancedEmbeddingService
embedding = AdvancedEmbeddingService.generate_embedding("image.jpg")

# Search also works (FAISS in memory)
from services.advanced_search import get_faiss_service
faiss_svc = get_faiss_service()
distances, indices = faiss_svc.search_vector(embedding, k=5)
```

Database is only needed if you want persistent image metadata storage.

---

## 📝 Quick Reference

| Mode | DB Required | Can Upload | Can Search | Persistent Storage |
|------|-----------|----------|---------|-----------------|
| Offline | No | ✅ | ✅ | ❌ (in-memory only) |
| PostgreSQL | ✅ | ✅ | ✅ | ✅ |

---

**Recommendation:** Start with offline mode, add PostgreSQL later if needed!
