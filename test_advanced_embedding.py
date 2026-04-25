#!/usr/bin/env python3
"""
Test Advanced Embedding System
Quick functionality tests for the advanced embedding pipeline
"""

import os
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_image(size=(224, 224), color=(100, 150, 200)):
    """Create a simple test image"""
    arr = np.ones((size[0], size[1], 3), dtype=np.uint8)
    arr[:, :] = color
    # Add a circle for variety
    cv2 = __import__('cv2')
    cv2.circle(arr, (112, 112), 50, (200, 100, 50), -1)
    return arr

def test_image_preprocessing():
    """Test image loading and preprocessing"""
    print("\n" + "="*60)
    print("🧪 Test 1: Image Preprocessing")
    print("="*60)
    
    try:
        from services.advanced_embedding import load_and_preprocess
        
        # Create test image
        test_img = create_test_image()
        from PIL import Image as PILImage
        pil_img = PILImage.fromarray(test_img)
        
        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            pil_img.save(f.name)
            temp_path = f.name
        
        # Test preprocessing
        result = load_and_preprocess(temp_path)
        
        if result is not None:
            print(f"✅ Image loaded: shape={result.shape}, dtype={result.dtype}")
            assert result.shape == (224, 224, 3), "Wrong shape"
            assert result.dtype == np.uint8, "Wrong dtype"
            print(f"✅ Preprocessing successful")
        else:
            print(f"❌ Preprocessing returned None")
            return False
        
        # Cleanup
        os.unlink(temp_path)
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_clip_embedding():
    """Test CLIP embedding extraction"""
    print("\n" + "="*60)
    print("🧪 Test 2: CLIP Embedding")
    print("="*60)
    
    try:
        from services.advanced_embedding import extract_clip_embedding, get_clip_model
        from PIL import Image as PILImage
        
        print("⏳ Loading CLIP model...")
        model = get_clip_model()
        print(f"✅ CLIP model loaded")
        
        # Create test image
        test_img = create_test_image()
        pil_img = PILImage.fromarray(test_img)
        
        print("⏳ Extracting CLIP embedding...")
        embedding = extract_clip_embedding(pil_img)
        
        if embedding is not None:
            print(f"✅ CLIP embedding: shape={embedding.shape}, dtype={embedding.dtype}")
            assert embedding.shape[0] == 512, "CLIP should output 512-dim"
            assert embedding.dtype == np.float32, "Wrong dtype"
            assert np.linalg.norm(embedding) > 0, "Zero embedding"
            print(f"✅ CLIP embedding successful")
            return True
        else:
            print(f"❌ CLIP extraction returned None")
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_traditional_features():
    """Test traditional feature extraction"""
    print("\n" + "="*60)
    print("🧪 Test 3: Traditional Features")
    print("="*60)
    
    try:
        from services.advanced_embedding import extract_traditional_features
        
        # Create test image
        test_img = create_test_image()
        
        print("⏳ Extracting traditional features...")
        color_v, bright_v, tex_v, edge_v, dom_v = extract_traditional_features(test_img)
        
        print(f"✅ Color features: shape={color_v.shape}")
        print(f"✅ Brightness features: shape={bright_v.shape}")
        print(f"✅ Texture features: shape={tex_v.shape}")
        print(f"✅ Edge features: shape={edge_v.shape}")
        print(f"✅ Dominant color features: shape={dom_v.shape}")
        
        # Verify all are normalized
        for v in [color_v, bright_v, tex_v, edge_v, dom_v]:
            norm = np.linalg.norm(v)
            assert 0.99 <= norm <= 1.01, f"Vector not L2-normalized: {norm}"
        
        print(f"✅ All features L2-normalized")
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_feature_combination():
    """Test feature combination and weighting"""
    print("\n" + "="*60)
    print("🧪 Test 4: Feature Combination")
    print("="*60)
    
    try:
        from services.advanced_embedding import combine_features, extract_traditional_features, extract_clip_embedding, get_clip_model
        from PIL import Image as PILImage
        
        # Create test image
        test_img = create_test_image()
        pil_img = PILImage.fromarray(test_img)
        
        # Get CLIP embedding
        model = get_clip_model()
        clip_emb = extract_clip_embedding(pil_img)
        
        # Get traditional features
        color_v, bright_v, tex_v, edge_v, dom_v = extract_traditional_features(test_img)
        
        # Combine
        combined = combine_features(clip_emb, color_v, bright_v, tex_v, edge_v, dom_v)
        
        print(f"✅ Combined embedding: shape={combined.shape}")
        
        # Verify
        assert combined.shape[0] > 400, "Combined should be large"
        assert combined.dtype == np.float32, "Wrong dtype"
        
        # Check normalization
        norm = np.linalg.norm(combined)
        assert 0.99 <= norm <= 1.01, f"Not normalized: {norm}"
        print(f"✅ Combined embedding normalized (norm={norm:.4f})")
        
        # Check no NaNs
        assert not np.isnan(combined).any(), "Contains NaN"
        print(f"✅ No NaN values")
        
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_full_pipeline():
    """Test complete embedding pipeline"""
    print("\n" + "="*60)
    print("🧪 Test 5: Full Embedding Pipeline")
    print("="*60)
    
    try:
        from services.advanced_embedding import AdvancedEmbeddingService
        from PIL import Image as PILImage
        import tempfile
        
        # Create test image
        test_img = create_test_image()
        pil_img = PILImage.fromarray(test_img)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            pil_img.save(f.name)
            temp_path = f.name
        
        print("⏳ Running full pipeline...")
        embedding = AdvancedEmbeddingService.generate_embedding(temp_path)
        
        if embedding is not None:
            print(f"✅ Generated embedding: shape={embedding.shape}")
            
            # Verify
            assert embedding.shape[0] > 400, "Should be large"
            assert embedding.dtype == np.float32, "Wrong dtype"
            
            # Check L2 norm
            norm = np.linalg.norm(embedding)
            assert 0.99 <= norm <= 1.01, f"Not normalized: {norm}"
            print(f"✅ Embedding normalized")
            
            # Check no NaNs
            assert not np.isnan(embedding).any(), "Contains NaN"
            print(f"✅ No NaN values")
            
            print(f"✅ Full pipeline successful")
            os.unlink(temp_path)
            return True
        else:
            print(f"❌ Pipeline returned None")
            os.unlink(temp_path)
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_faiss_search():
    """Test FAISS indexing and search"""
    print("\n" + "="*60)
    print("🧪 Test 6: FAISS Search")
    print("="*60)
    
    try:
        from services.advanced_search import AdvancedFAISSService
        
        print("⏳ Creating FAISS index...")
        faiss_svc = AdvancedFAISSService()
        
        # Create random vectors
        np.random.seed(42)
        vectors = np.random.randn(10, 632).astype(np.float32)
        # L2 normalize
        vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        
        print(f"✅ Created test vectors: shape={vectors.shape}")
        
        # Add to index
        print("⏳ Adding vectors to FAISS...")
        indices = faiss_svc.add_vectors(vectors)
        print(f"✅ Added {len(indices)} vectors")
        
        # Search
        query = vectors[0].reshape(1, -1)
        print("⏳ Searching...")
        distances, result_indices = faiss_svc.search_vector(query, k=3)
        
        print(f"✅ Search results:")
        print(f"   Indices: {result_indices}")
        print(f"   Distances: {distances}")
        
        # First result should be the query itself
        assert result_indices[0] == 0, "First result should be the query"
        print(f"✅ FAISS search successful")
        
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print(f"\n{'🧪 ADVANCED EMBEDDING SYSTEM TEST SUITE':^60}\n")
    
    tests = [
        ("Image Preprocessing", test_image_preprocessing),
        ("CLIP Embedding", test_clip_embedding),
        ("Traditional Features", test_traditional_features),
        ("Feature Combination", test_feature_combination),
        ("Full Pipeline", test_full_pipeline),
        ("FAISS Search", test_faiss_search),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} {name}")
    
    print(f"\n📈 Results: {passed}/{total} passed")
    
    if passed == total:
        print(f"\n🎉 ALL TESTS PASSED! Your system is ready.")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check output above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
