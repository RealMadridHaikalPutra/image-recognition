"""
Quick start guide and verification script
Run this to test your installation
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_dependencies():
    """Check if all required packages are installed"""
    print("\n📦 Checking Dependencies...\n")
    
    dependencies = [
        ('flask', 'Flask'),
        ('numpy', 'NumPy'),
        ('PIL', 'Pillow'),
        ('faiss', 'FAISS'),
        ('psycopg2', 'psycopg2'),
    ]
    
    missing = []
    
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"✓ {name}")
        except ImportError:
            print(f"✗ {name} - NOT INSTALLED")
            missing.append(name)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print(f"Install with: pip install -r requirements.txt")
        return False
    
    print("\n✅ All dependencies installed!\n")
    return True


def check_directories():
    """Check if required directories exist"""
    print("📁 Checking Directories...\n")
    
    directories = [
        'uploads',
        'embeddings',
        'templates',
        'static/css',
        'static/js',
        'services',
        'models',
        'utils',
    ]
    
    for directory in directories:
        dir_path = project_root / directory
        if dir_path.exists():
            print(f"✓ {directory}/")
        else:
            print(f"✗ {directory}/ - MISSING")
            return False
    
    print("\n✅ All directories exist!\n")
    return True


def check_files():
    """Check if required files exist"""
    print("📄 Checking Files...\n")
    
    files = [
        'app.py',
        'config.py',
        'requirements.txt',
        'README.md',
        'models/db.py',
        'services/embedding.py',
        'services/search.py',
        'services/storage.py',
        'utils/helpers.py',
        'templates/index.html',
        'templates/upload.html',
        'templates/search.html',
        'static/css/style.css',
        'static/js/main.js',
    ]
    
    for file in files:
        file_path = project_root / file
        if file_path.exists():
            print(f"✓ {file}")
        else:
            print(f"✗ {file} - MISSING")
            return False
    
    print("\n✅ All files exist!\n")
    return True


def check_database():
    """Check PostgreSQL connection"""
    print("🗄️  Checking Database Connection...\n")
    
    try:
        import psycopg2
        import config
        
        # Try to connect
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.close()
        print(f"✓ PostgreSQL connection successful")
        print(f"  Host: {config.DB_HOST}")
        print(f"  Port: {config.DB_PORT}")
        print(f"  Database: {config.DB_NAME}")
        print(f"  User: {config.DB_USER}")
        print("\n✅ Database is ready!\n")
        return True
    
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print(f"\n⚠️  Make sure PostgreSQL is running and .env is configured")
        print(f"Database URL: {config.DATABASE_URL}\n")
        return False


def test_embedding_service():
    """Test embedding service"""
    print("🧠 Testing Embedding Service...\n")
    
    try:
        from services.embedding import EmbeddingService
        from PIL import Image
        import numpy as np
        
        # Create test image
        test_img = Image.new('RGB', (224, 224), color='red')
        test_path = project_root / 'uploads' / 'test_image.jpg'
        test_img.save(str(test_path))
        
        # Generate embedding
        embedding = EmbeddingService.generate_embedding(str(test_path))
        
        print(f"✓ Embedding generated successfully")
        print(f"  Shape: {embedding.shape}")
        print(f"  Dtype: {embedding.dtype}")
        print(f"  Min value: {embedding.min():.4f}")
        print(f"  Max value: {embedding.max():.4f}")
        
        # Cleanup
        test_path.unlink()
        
        print("\n✅ Embedding service works!\n")
        return True
    
    except Exception as e:
        print(f"✗ Embedding test failed: {e}")
        print("\n")
        return False


def test_faiss_service():
    """Test FAISS service"""
    print("🔍 Testing FAISS Service...\n")
    
    try:
        from services.search import faiss_service
        import numpy as np
        
        # Test adding and searching vectors
        test_vector = np.random.randn(512).astype(np.float32)
        
        # Add vector
        idx = faiss_service.add_vector(test_vector)
        print(f"✓ Vector added to index")
        print(f"  FAISS index: {idx}")
        
        # Search
        distances, indices = faiss_service.search_vector(test_vector, k=1)
        print(f"✓ Search successful")
        print(f"  Found {len(indices)} result(s)")
        print(f"  Distance: {distances[0]:.6f}")
        
        print("\n✅ FAISS service works!\n")
        return True
    
    except Exception as e:
        print(f"✗ FAISS test failed: {e}")
        print("\n")
        return False


def main():
    """Run all checks"""
    print("""
    ╔════════════════════════════════════════════════╗
    ║  🎯 Installation Verification Script         ║
    ║  Image-Based Product Search System           ║
    ╚════════════════════════════════════════════════╝
    """)
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Directories", check_directories),
        ("Files", check_files),
        ("Database", check_database),
        ("Embedding Service", test_embedding_service),
        ("FAISS Service", test_faiss_service),
    ]
    
    results = []
    
    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            print(f"⚠️  {name} check failed with error: {e}\n")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*50)
    print("📊 VERIFICATION SUMMARY")
    print("="*50 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {name}")
    
    print(f"\nResult: {passed}/{total} checks passed\n")
    
    if passed == total:
        print("🎉 All checks passed! You're ready to go!\n")
        print("Start the application with:")
        print("  python app.py\n")
        print("Then visit: http://localhost:5000\n")
        return 0
    else:
        print("⚠️  Some checks failed. Please fix the issues above.\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
