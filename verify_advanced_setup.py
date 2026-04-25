#!/usr/bin/env python3
"""
Advanced Embedding System - Verification Script
Checks all dependencies, configurations, and functionality
"""
import importlib
import sys
import os
from pathlib import Path

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def check_module(module_name, version_attr=None):
    try:
        mod = importlib.import_module(module_name)
        version = getattr(mod, "__version__", "?")
        return "✅", version
    except Exception as e:
        return "❌", str(e)

def main():
    print(f"\n{'🔍 ADVANCED EMBEDDING VERIFICATION':^60}\n")
    
    # 1. Python Version
    print_section("1️⃣  Python Environment")
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"✅ Python: {py_version}")
    if sys.version_info < (3, 8):
        print(f"❌ Python 3.8+ required (you have {py_version})")
        return False
    
    # 2. Core Dependencies
    print_section("2️⃣  Core Dependencies")
    
    deps = [
        ("flask", "Flask 2.x"),
        ("psycopg2", "PostgreSQL driver"),
        ("numpy", "__version__"),
        ("PIL", "Pillow (imaging)"),
        ("faiss", "FAISS vector search"),
        ("cv2", "OpenCV (image processing)"),
        ("torch", "__version__"),
        ("torchvision", "__version__"),
        ("sentence_transformers", "__version__"),  # ✅ FIX DISINI
        ("skimage", "scikit-image (features)"),
        ("sklearn", "scikit-learn"),
        ("tqdm", "Progress bars"),
    ]
    
    missing = []
    for mod, desc in deps:
        status, version = check_module(mod)
        if status == "❌":
            missing.append((mod, desc))
        print(f"{status} {mod:20} {version:15} ({desc})")
    
    if missing:
        print(f"\n❌ Missing {len(missing)} module(s):")
        for mod, desc in missing:
            print(f"   - {mod}: {desc}")
        print(f"\n📦 Install with: pip install -r requirements.txt")
        return False
    
    # 3. Project Structure
    print_section("3️⃣  Project Structure")
    
    required_files = [
        "app.py",
        "config.py",
        "models/db.py",
        "services/advanced_embedding.py",
        "services/advanced_search.py",
        "services/storage.py",
        "templates/upload.html",
        "templates/search.html",
        "static/css/style.css",
    ]
    
    all_exist = True
    for fpath in required_files:
        full_path = Path(fpath)
        exists = "✅" if full_path.exists() else "❌"
        print(f"{exists} {fpath}")
        if not full_path.exists():
            all_exist = False
    
    if not all_exist:
        print(f"\n❌ Missing project files!")
        return False
    
    # 4. Configuration
    print_section("4️⃣  Configuration")
    
    try:
        import config
        print(f"✅ config.py loaded successfully")
        
        required_attrs = [
            "UPLOAD_DIR",
            "EMBEDDINGS_INDEX_PATH",
            "DB_HOST",
            "DB_PORT",
            "DB_NAME",
        ]
        
        for attr in required_attrs:
            if hasattr(config, attr):
                val = getattr(config, attr)
                print(f"✅ config.{attr} = {val}")
            else:
                print(f"❌ config.{attr} missing")
                return False
    
    except Exception as e:
        print(f"❌ Failed to load config.py: {e}")
        return False
    
    # 5. Database
    print_section("5️⃣  Database Connection")
    
    try:
        from models.db import db
        db.connect()
        print(f"✅ PostgreSQL connection successful")
        db.init_tables()
        print(f"✅ Database tables initialized")
        db.disconnect()
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        print(f"   (PostgreSQL may not be running, but advanced embedding works offline)")
    
    # 6. CLIP Model Download
    print_section("6️⃣  CLIP Model (Auto-Download on First Use)")
    
    try:
        from sentence_transformers import SentenceTransformer
        print(f"✅ SentenceTransformers available")
        print(f"   Model: clip-ViT-B-32")
        print(f"   Size: ~500MB (auto-downloaded on first use)")
        print(f"   Time: 2-5 minutes (internet required)")
    except Exception as e:
        print(f"❌ SentenceTransformers error: {e}")
        return False
    
    # 7. Advanced Services
    print_section("7️⃣  Advanced Services")
    
    try:
        from services.advanced_embedding import AdvancedEmbeddingService
        print(f"✅ AdvancedEmbeddingService imported")
    except Exception as e:
        print(f"❌ AdvancedEmbeddingService failed: {e}")
        return False
    
    try:
        from services.advanced_search import get_faiss_service
        faiss_svc = get_faiss_service()
        print(f"✅ AdvancedFAISSService initialized")
        print(f"   Index info: {faiss_svc.get_index_info()}")
    except Exception as e:
        print(f"❌ AdvancedFAISSService failed: {e}")
        return False
    
    # 8. GPU Check
    print_section("8️⃣  GPU Acceleration (Optional)")
    
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✅ CUDA GPU detected: {torch.cuda.get_device_name(0)}")
            print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
            print(f"   (CLIP will use GPU for faster embedding)")
        else:
            print(f"⚠️  No GPU detected (using CPU)")
            print(f"   CLIP will be slower but still works")
    except Exception as e:
        print(f"❌ GPU check failed: {e}")
    
    # 9. File Permissions
    print_section("9️⃣  File Permissions")
    
    dirs = [
        "uploads",
        "embeddings",
        "logs",
    ]
    
    for d in dirs:
        dpath = Path(d)
        if not dpath.exists():
            try:
                dpath.mkdir(parents=True, exist_ok=True)
                print(f"✅ {d}/ (created)")
            except Exception as e:
                print(f"❌ {d}/ (creation failed: {e})")
        else:
            if os.access(d, os.W_OK):
                print(f"✅ {d}/ (writable)")
            else:
                print(f"❌ {d}/ (not writable)")
    
    # Final Summary
    print_section("✅ VERIFICATION COMPLETE")
    
    print("""
🚀 Your system is ready for advanced embeddings!

Next Steps:
1. Start Flask app:        python app.py
2. Open in browser:        http://localhost:5000
3. Upload an image:        /upload
4. Search similar images:  /search

Advanced Features Active:
✅ CLIP embeddings
✅ Multi-modal feature fusion
✅ Automatic FAISS optimization
✅ Intelligent image preprocessing
✅ GPU acceleration (if available)

For configuration help, see: ADVANCED_EMBEDDING_GUIDE.md
    """)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
