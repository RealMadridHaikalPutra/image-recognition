Quick Start Guide
==================

🎯 Image-Based Product Search System

📋 REQUIREMENTS
- Python 3.8+
- PostgreSQL 12+
- 500MB free disk space

---

⚡ QUICK START (5 MINUTES)

1. INSTALL DEPENDENCIES
   ─────────────────────────────────────────
   
   # Create virtual environment
   python -m venv venv
   
   # Activate it
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   
   # Install packages
   pip install -r requirements.txt


2. SETUP DATABASE
   ─────────────────────────────────────────
   
   # Create PostgreSQL database
   createdb image_search
   
   # Verify (should show image_search in list)
   psql -l


3. CONFIGURE ENVIRONMENT
   ─────────────────────────────────────────
   
   # Copy example .env
   cp .env.example .env
   
   # (Optional) Edit .env if using non-default settings
   # cat .env


4. VERIFY INSTALLATION
   ─────────────────────────────────────────
   
   python verify_installation.py
   
   Should show: ✅ All checks passed!


5. START APPLICATION
   ─────────────────────────────────────────
   
   python app.py
   
   Should show:
   ╔════════════════════════════════════════════════╗
   ║  🎯 Image-Based Product Search System         ║
   ╚════════════════════════════════════════════════╝
   🚀 Starting Flask application...


6. OPEN IN BROWSER
   ─────────────────────────────────────────
   
   http://localhost:5000
   
   You should see the home page with:
   - 📦 Total Items: 0
   - 🖼️ Total Images: 0
   - 🧠 Embeddings: 0
   - 💾 Storage Used: 0 MB


---

✅ TEST THE SYSTEM

1. UPLOAD A TEST IMAGE
   ─────────────────────────────────────────
   
   1. Click "Upload" in navigation
   2. Enter Product ID: TEST-001
   3. Select Angle: front
   4. Click "Choose File" and select an image
   5. Click "Upload Image"
   
   Wait for success message ✅


2. UPLOAD ANOTHER IMAGE (DIFFERENT ANGLE)
   ─────────────────────────────────────────
   
   1. Product ID: TEST-001 (same product!)
   2. Angle: back
   3. Upload different image
   
   Now you have 2 images of the same product


3. SEARCH FOR SIMILAR IMAGES
   ─────────────────────────────────────────
   
   1. Click "Search" in navigation
   2. Click "Choose File" and select the first image
   3. Click "Search Similar Products"
   
   Should show:
   - TEST-001 with high similarity score (80-100%)
   - 2 matched images


4. CHECK STATISTICS
   ─────────────────────────────────────────
   
   Go back to Home page. Stats should show:
   - 📦 Total Items: 1
   - 🖼️ Total Images: 2
   - 🧠 Embeddings: 2
   - 💾 Storage Used: ~1-5 MB


---

🐛 COMMON ISSUES & SOLUTIONS

Issue: "Connection refused" / "could not connect to server"
Solution:
  1. Check PostgreSQL is running
  2. On Windows: Services > PostgreSQL > right-click > Start
  3. On macOS: brew services start postgresql
  4. On Linux: sudo service postgresql start


Issue: "No module named 'flask'"
Solution:
  1. Activate virtual environment
  2. Run: pip install -r requirements.txt


Issue: "Index.faiss not found"
Solution:
  1. First upload will create it automatically
  2. Or restart application after first upload


Issue: "Database 'image_search' does not exist"
Solution:
  1. Run: createdb image_search
  2. Or: psql -U postgres -c "CREATE DATABASE image_search;"


---

📊 API TESTING

Get all items (JSON API):
  curl http://localhost:5000/api/items

Get item details:
  curl http://localhost:5000/api/item/TEST-001

Get statistics:
  curl http://localhost:5000/api/stats


---

🚀 NEXT STEPS

1. Read README.md for detailed documentation
2. Run test_system.py to test all components
3. Upload more product images
4. Test search functionality
5. Review database with: psql -d image_search


---

📁 PROJECT STRUCTURE

Key files to know:
  app.py                 ← Main application
  config.py              ← Configuration
  requirements.txt       ← Dependencies
  
  models/db.py           ← Database operations
  services/embedding.py  ← Image embedding
  services/search.py     ← FAISS search
  services/storage.py    ← File storage
  
  templates/             ← HTML pages
  static/                ← CSS & JavaScript


---

💡 TIPS

- Use PROD-001, PROD-002, etc. for real data
- Upload 3-4 angles per product for best results
- Supported formats: JPEG, PNG, GIF (max 10MB)
- Search results colored: 🟢 Green = High, 🟡 Yellow = Medium, 🟠 Orange = Low


---

📚 DOCUMENTATION

For more details, see:
  - README.md         ← Full documentation
  - config.py         ← Configuration options
  - app.py            ← Route documentation


---

Need help? Check the logs or run:
  python verify_installation.py
  python test_system.py


Happy searching! 🔍
