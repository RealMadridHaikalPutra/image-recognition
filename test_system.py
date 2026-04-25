"""
Test script to verify the complete system end-to-end
"""

import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_upload_pipeline():
    """Test complete upload pipeline"""
    print("\n" + "="*50)
    print("📤 TEST: Upload Pipeline")
    print("="*50)
    
    try:
        from models.db import db
        from services.embedding import EmbeddingService
        from services.search import faiss_service
        from services.storage import storage_service
        from PIL import Image
        import numpy as np
        
        # Connect to database
        db.connect()
        
        # Create test image
        print("\n1️⃣ Creating test image...")
        test_img = Image.new('RGB', (224, 224), color=(255, 0, 0))
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
            test_img.save(tmp_path)
        print(f"   ✓ Test image created: {tmp_path}")
        
        # Test storage
        print("\n2️⃣ Testing file storage...")
        from werkzeug.datastructures import FileStorage
        from io import BytesIO
        
        file_stream = BytesIO(open(tmp_path, 'rb').read())
        file_obj = FileStorage(stream=file_stream, filename='test.jpg')
        
        save_result = storage_service.save_image(file_obj, 'TEST-001', 'front')
        print(f"   ✓ File saved: {save_result['file_path']}")
        
        # Test database insert
        print("\n3️⃣ Testing database operations...")
        image_id = db.insert_image('TEST-001', save_result['file_path'], 'front')
        print(f"   ✓ Image metadata saved: id={image_id}")
        
        # Test embedding
        print("\n4️⃣ Testing embedding generation...")
        embedding = EmbeddingService.generate_embedding(save_result['full_path'])
        print(f"   ✓ Embedding generated: shape={embedding.shape}, dtype={embedding.dtype}")
        
        # Test FAISS
        print("\n5️⃣ Testing FAISS indexing...")
        faiss_idx = faiss_service.add_vector(embedding)
        print(f"   ✓ Vector added to FAISS: index={faiss_idx}")
        
        # Test embedding metadata
        print("\n6️⃣ Testing embedding metadata storage...")
        embedding_id = db.insert_embedding(image_id, 'TEST-001', faiss_idx)
        print(f"   ✓ Embedding metadata saved: id={embedding_id}")
        
        # Save FAISS
        print("\n7️⃣ Persisting FAISS index...")
        faiss_service.save_index()
        print(f"   ✓ FAISS index persisted")
        
        # Cleanup
        os.unlink(tmp_path)
        
        print("\n✅ Upload pipeline test PASSED!\n")
        return True
    
    except Exception as e:
        print(f"\n❌ Upload pipeline test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            db.disconnect()
        except:
            pass


def test_search_pipeline():
    """Test complete search pipeline"""
    print("\n" + "="*50)
    print("🔍 TEST: Search Pipeline")
    print("="*50)
    
    try:
        from models.db import db
        from services.embedding import EmbeddingService
        from services.search import faiss_service
        from PIL import Image
        import numpy as np
        
        # Connect to database
        db.connect()
        
        # Check if we have embeddings
        embedding_count = db.count_embeddings()
        if embedding_count == 0:
            print("\n⚠️ No embeddings in database. Run upload test first.")
            db.disconnect()
            return False
        
        print(f"\n1️⃣ Database contains {embedding_count} embeddings")
        
        # Create query image
        print("\n2️⃣ Creating query image...")
        test_img = Image.new('RGB', (224, 224), color=(255, 0, 0))
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
            test_img.save(tmp_path)
        print(f"   ✓ Query image created")
        
        # Generate query embedding
        print("\n3️⃣ Generating query embedding...")
        query_embedding = EmbeddingService.generate_embedding(tmp_path)
        print(f"   ✓ Query embedding generated: shape={query_embedding.shape}")
        
        # Search FAISS
        print("\n4️⃣ Searching FAISS index...")
        distances, indices = faiss_service.search_vector(query_embedding, k=5)
        print(f"   ✓ Found {len(indices)} results")
        for i, (idx, dist) in enumerate(zip(indices, distances)):
            print(f"      Result {i+1}: FAISS index={idx}, distance={dist:.4f}")
        
        # Map to items
        print("\n5️⃣ Mapping FAISS indices to items...")
        faiss_mapping = db.get_faiss_to_item_mapping()
        item_votes = {}
        
        for faiss_idx, distance in zip(indices, distances):
            faiss_idx = int(faiss_idx)
            if faiss_idx in faiss_mapping:
                item_id = faiss_mapping[faiss_idx]
                if item_id not in item_votes:
                    item_votes[item_id] = 0
                item_votes[item_id] += 1
                print(f"   Mapped: FAISS {faiss_idx} → {item_id}")
        
        # Sort results
        print("\n6️⃣ Ranking results...")
        sorted_items = sorted(item_votes.items(), key=lambda x: -x[1])
        for item_id, votes in sorted_items[:3]:
            print(f"   {item_id}: {votes} vote(s)")
        
        # Cleanup
        os.unlink(tmp_path)
        
        print("\n✅ Search pipeline test PASSED!\n")
        return True
    
    except Exception as e:
        print(f"\n❌ Search pipeline test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            db.disconnect()
        except:
            pass


def main():
    """Run all tests"""
    print("""
    ╔════════════════════════════════════════════════╗
    ║  🧪 End-to-End System Test                    ║
    ║  Image-Based Product Search System           ║
    ╚════════════════════════════════════════════════╝
    """)
    
    tests = [
        test_upload_pipeline,
        test_search_pipeline,
    ]
    
    results = []
    
    for test_fn in tests:
        try:
            result = test_fn()
            results.append((test_fn.__name__, result))
        except Exception as e:
            print(f"\n⚠️  {test_fn.__name__} failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_fn.__name__, False))
    
    # Summary
    print("\n" + "="*50)
    print("🧪 TEST SUMMARY")
    print("="*50 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {name}")
    
    print(f"\nResult: {passed}/{total} tests passed\n")
    
    if passed == total:
        print("🎉 All tests passed! System is working correctly!\n")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the errors above.\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
