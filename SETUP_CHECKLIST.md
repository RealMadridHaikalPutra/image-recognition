# ✅ SETUP CHECKLIST: Advanced Embedding System

Complete this checklist to get your advanced image search system running.

---
 
## 📦 Phase 1: Dependencies (5 minutes)

### Step 1.1: Update pip (optional but recommended)
```bash
python -m pip install --upgrade pip
```
- [ ] Done

### Step 1.2: Install Requirements
```bash
pip install -r requirements.txt
```

This installs:
- Flask 2.3.2 (web framework)
- PyTorch 2.0.1 (CLIP model)
- SentenceTransformers 2.2.2 (CLIP interface)
- OpenCV 4.8.0 (image processing)
- FAISS 1.7.4 (similarity search)
- PostgreSQL driver (database)
- And 8 more supporting libraries

- [ ] Installation complete
- [ ] No errors during installation

### Step 1.3: Verify Installation
```bash
python verify_advanced_setup.py
```

Expected output: Green checkmarks ✅ for all components

- [ ] All modules found
- [ ] Configuration loaded
- [ ] Database optional (can be skipped for initial testing)
- [ ] CLIP model recognized (will download on first use)

---

## 🔧 Phase 2: Configuration (2 minutes)

### Step 2.1: Check Database (Optional)
If you want PostgreSQL functionality (not required for initial testing):

**Linux/Mac:**
```bash
brew install postgresql
brew services start postgresql
```

**Windows:**
- Download from https://www.postgresql.org/download/windows/
- Or use WSL2 with Ubuntu

**Verify:**
```bash
psql --version
```

- [ ] PostgreSQL running (optional)
- [ ] or willing to use without DB for now

### Step 2.2: Check Configuration
Edit `config.py`:

```python
# Database (optional for testing)
DB_HOST = 'localhost'
DB_NAME = 'image_search'
DB_USER = 'postgres'
DB_PASSWORD = 'postgres'

# Should be fine as-is for local development
```

- [ ] config.py reviewed
- [ ] Database settings OK (or will test without)

---

## 🧪 Phase 3: Testing (5 minutes)

### Step 3.1: Run Unit Tests
```bash
python test_advanced_embedding.py
```

Expected: 6/6 tests pass ✅

Tests check:
1. Image preprocessing
2. CLIP embedding extraction
3. Traditional feature extraction
4. Feature combination
5. Complete embedding pipeline
6. FAISS search

- [ ] Image Preprocessing: PASS
- [ ] CLIP Embedding: PASS (downloads model on first run)
- [ ] Traditional Features: PASS
- [ ] Feature Combination: PASS
- [ ] Full Pipeline: PASS
- [ ] FAISS Search: PASS

**Note:** First CLIP test will download ~500MB model (2-5 min), then be instant.

---

## 🚀 Phase 4: Starting the Application (2 minutes)

### Step 4.1: Start Flask Server
```bash
python app.py
```

Expected output:
```
 * Running on http://127.0.0.1:5000
```

- [ ] Server started successfully
- [ ] Listening on http://localhost:5000

### Step 4.2: Open in Browser
Visit: **http://localhost:5000**

You should see the home page with:
- Upload section
- Search section
- Statistics

- [ ] Home page loads
- [ ] All UI elements visible

---

## 📸 Phase 5: Test Functionality (5 minutes)

### Step 5.1: Upload First Image
1. Go to http://localhost:5000/upload
2. Enter:
   - Product ID: `TEST-001`
   - Angle: `0`
   - Choose an image file (JPG, PNG, or GIF)
3. Click Upload

Expected:
- Image processes (may take 20-30 sec on first load due to CLIP model download)
- Success message appears
- Behind scenes: Advanced embedding generated and indexed

- [ ] Image uploaded successfully
- [ ] CLIP model downloaded (if first time)
- [ ] No errors in console

### Step 5.2: Upload Second Image
1. Upload another image (different product or different angle)
2. Enter:
   - Product ID: `TEST-002`
   - Angle: `0` or `90`
3. Click Upload

- [ ] Second image uploaded
- [ ] Takes 3-5 seconds (CLIP model cached)

### Step 5.3: Test Search
1. Go to http://localhost:5000/search
2. Upload the first image as query
3. Click Search

Expected:
- Should find similar images
- Shows similarity scores
- Lists matching products

- [ ] Search works
- [ ] Results displayed with scores
- [ ] First/same image ranks highest

---

## 🎯 Phase 6: Advanced Features (Optional)

### Step 6.1: Customize Feature Weights
Edit `services/advanced_embedding.py`:

```python
class AdvancedEmbeddingConfig:
    WEIGHT_CLIP = 0.45           # Semantic importance (0.0-1.0)
    WEIGHT_COLOR = 0.30          # Color importance
    WEIGHT_TEXTURE = 0.12        # Texture/detail importance
    # ... other weights
    # SUM MUST EQUAL 1.0
```

Examples:
- **Fashion focus**: `WEIGHT_COLOR = 0.40`
- **Technical focus**: `WEIGHT_TEXTURE = 0.20`
- **More semantic**: `WEIGHT_CLIP = 0.50`

- [ ] Reviewed weight configuration
- [ ] Understood impact on results

### Step 6.2: Rebuild Index from Existing Images
If you have many images already uploaded:

```bash
python build_advanced_index.py
```

This will:
1. Load all images from `uploads/`
2. Regenerate embeddings with current weights
3. Rebuild FAISS index
4. Update database

- [ ] Understood purpose of rebuild script
- [ ] Know when to use it (after weight changes)

### Step 6.3: Check GPU Status
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
```

- [ ] Checked GPU status
- [ ] Understood speedup (GPU ~5x faster)

---

## 📚 Phase 7: Documentation Review (Optional)

Read these for deeper understanding:

1. **ADVANCED_EMBEDDING_GUIDE.md** (20 min read)
   - [ ] Overview and features
   - [ ] Configuration details
   - [ ] Performance tuning
   - [ ] Troubleshooting

2. **API_REFERENCE.md** (10 min read)
   - [ ] Function signatures
   - [ ] Code examples
   - [ ] Common patterns

3. **INTEGRATION_SUMMARY.md** (5 min read)
   - [ ] What's new
   - [ ] Architecture overview
   - [ ] Quick reference

---

## 🎉 Phase 8: Deployment (Production)

### Step 8.1: Install Production Server (Optional)
```bash
pip install gunicorn
```

### Step 8.2: Run with Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Step 8.3: Add to Systemd (Linux)
Create `/etc/systemd/system/image-search.service`:

```ini
[Unit]
Description=Image Search Service
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/gunicorn -w 4 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable image-search
sudo systemctl start image-search
```

- [ ] Production deployment planned
- [ ] Or: Development mode is sufficient for now

---

## 🆘 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'torch'"
```bash
# Solution: Reinstall requirements
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: "CUDA out of memory"
```python
# Solution: Edit services/advanced_embedding.py
AdvancedEmbeddingConfig.BATCH_SIZE = 8  # Reduced from 32
# Or use CPU only
AdvancedEmbeddingConfig.DEVICE = "cpu"
```

### Issue: "ConnectionError: CLIP model download failed"
- Solution: Check internet connection
- Solution: Manually download model:
  ```python
  from sentence_transformers import SentenceTransformer
  SentenceTransformer("clip-ViT-B-32")
  ```

### Issue: "FAISS index corrupted"
```bash
# Solution: Rebuild index
python build_advanced_index.py
```

### Issue: "Search returns no results"
- Solution: Ensure images are uploaded first
- Solution: Check database connection
- Solution: Check FAISS index size: visit `/api/stats`

---

## ✅ Final Checklist

Before considering setup complete:

- [ ] Phase 1: Dependencies installed
- [ ] Phase 2: Configuration checked
- [ ] Phase 3: Tests passed (6/6)
- [ ] Phase 4: Server starts
- [ ] Phase 5: Upload and search work
- [ ] Phase 6: (Optional) Advanced features reviewed
- [ ] Phase 7: (Optional) Documentation read
- [ ] Phase 8: (Optional) Deployment considered
- [ ] Phase 8.1: (Optional) Troubleshooting skimmed

---

## 🎯 Next Actions

**If everything is working:**
1. Upload your actual product images
2. Test search quality
3. Adjust feature weights if needed
4. Deploy to production

**If something isn't working:**
1. Check troubleshooting section above
2. Read ADVANCED_EMBEDDING_GUIDE.md
3. Run verify_advanced_setup.py again
4. Check logs for error details

---

## 📞 Support Resources

- **Quick Start**: QUICKSTART.md
- **Complete Guide**: ADVANCED_EMBEDDING_GUIDE.md
- **API Reference**: API_REFERENCE.md
- **Setup Details**: COMPLETE_SETUP.md
- **Troubleshooting**: ADVANCED_EMBEDDING_GUIDE.md (Troubleshooting section)

---

**Congratulations!** 🎉

Your advanced image search system with CLIP embeddings is ready!

Estimated time to complete: **~20-30 minutes**

Start with Phase 1 and work your way through! ✨
