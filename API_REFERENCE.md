# 📖 API Reference: Advanced Embedding System

## Quick Reference for Developers

### AdvancedEmbeddingService

Generate embeddings from images:

```python
from services.advanced_embedding import AdvancedEmbeddingService

# Single image
embedding = AdvancedEmbeddingService.generate_embedding("path/to/image.jpg")
# Returns: np.ndarray (1000-dim, float32, L2-normalized)

# Batch of images
embeddings = AdvancedEmbeddingService.generate_batch_embeddings([
    "path/to/image1.jpg",
    "path/to/image2.jpg",
])
# Returns: np.ndarray (n_images, 1000, float32)

# From PIL Image
from PIL import Image
img = Image.open("photo.jpg")
embedding = AdvancedEmbeddingService.generate_embedding(img)

# From numpy array
import numpy as np
img_array = np.array([...])  # Shape (H, W, 3), uint8
embedding = AdvancedEmbeddingService.generate_embedding(img_array)

# From bytes
with open("photo.jpg", "rb") as f:
    img_bytes = f.read()
embedding = AdvancedEmbeddingService.generate_embedding(img_bytes)
```

---

### AdvancedFAISSService

Manage vector indices:

```python
from services.advanced_search import get_faiss_service

faiss_svc = get_faiss_service()  # Singleton instance

# Add single vector
idx = faiss_svc.add_vector(embedding)
# Returns: int (FAISS index)

# Add multiple vectors
indices = faiss_svc.add_vectors(embeddings_array)
# Returns: list of int

# Search for similar vectors
distances, result_indices = faiss_svc.search_vector(query_embedding, k=5)
# Returns: (distances: array, indices: array)

# Search multiple queries
distances, result_indices = faiss_svc.search_vectors(queries, k=5)
# Returns: (distances: (n_queries, k), indices: (n_queries, k))

# Persistence
faiss_svc.save_index()        # Save to config.EMBEDDINGS_INDEX_PATH
faiss_svc.load_index()        # Load from disk
faiss_svc.reset_index()       # Clear index

# Info
info = faiss_svc.get_index_info()
# Returns: dict with ntotal, dimension, type, path
```

---

### Feature Extraction Functions

Manual feature extraction (for advanced use):

```python
from services.advanced_embedding import (
    load_and_preprocess,
    extract_clip_embedding,
    extract_traditional_features,
    combine_features,
    extract_clip_batch,
    get_clip_model,
)

# 1. Load and preprocess image
img_cv = load_and_preprocess("path/to/image.jpg")
# Returns: np.ndarray (224, 224, 3) or None

# 2. Extract CLIP embedding (single)
clip_emb = extract_clip_embedding(img_pil)
# Input: PIL Image
# Returns: np.ndarray (384,) L2-normalized

# 3. Extract CLIP batch (faster with GPU)
clip_embs = extract_clip_batch([img1, img2, img3])
# Input: list of PIL Images
# Returns: np.ndarray (n, 384)

# 4. Extract traditional features
color_v, bright_v, tex_v, edge_v, dom_v = extract_traditional_features(img_cv)
# Input: numpy array (H, W, 3)
# Returns: 5 L2-normalized feature vectors

# 5. Combine features with weights
final = combine_features(clip_emb, color_v, bright_v, tex_v, edge_v, dom_v)
# Returns: np.ndarray (~1000,) L2-normalized

# Get CLIP model directly
model = get_clip_model()
# Returns: SentenceTransformer instance (cached)
```

---

### Configuration

```python
from services.advanced_embedding import AdvancedEmbeddingConfig

# Read current config
cfg = AdvancedEmbeddingConfig
cfg.WEIGHT_CLIP           # 0.45 (45% semantic)
cfg.WEIGHT_COLOR          # 0.30 (30% color)
cfg.WEIGHT_BRIGHTNESS     # 0.08 (8% brightness)
cfg.WEIGHT_TEXTURE        # 0.12 (12% texture)
cfg.WEIGHT_EDGE           # 0.05 (5% edges)
cfg.WEIGHT_DOMINANT       # 0.15 (15% colors)
cfg.IMAGE_SIZE            # (224, 224)
cfg.BATCH_SIZE            # 32
cfg.MODEL_NAME            # "clip-ViT-B-32"
cfg.DEVICE                # "cuda" or "cpu"

# Modify weights (edit file services/advanced_embedding.py)
# Weights must sum to 1.0
```

---

### Database Integration

```python
from models.db import db

# Insert image metadata
image_id = db.insert_image(item_id="SKU-123", file_path="uploads/...", angle=0)

# Insert embedding mapping
db.insert_embedding(image_id=image_id, item_id="SKU-123", faiss_index=42)

# Get mapping for search
mapping = db.get_faiss_to_item_mapping()  # {faiss_idx: item_id}

# Get all images for item
images = db.get_item_details(item_id="SKU-123")
# Returns: list of {id, item_id, file_path, angle, created_at}
```

---

### Common Patterns

#### Pattern 1: Upload with embedding
```python
@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['image']
    
    # Save image
    path = storage_service.save_image(file, item_id, angle)
    
    # Generate embedding
    embedding = AdvancedEmbeddingService.generate_embedding(path['full_path'])
    
    # Add to FAISS
    faiss_idx = faiss_service.add_vector(embedding)
    
    # Store in DB
    image_id = db.insert_image(item_id, path['file_path'], angle)
    db.insert_embedding(image_id, item_id, faiss_idx)
    faiss_service.save_index()
    
    return "Success"
```

#### Pattern 2: Search similar
```python
@app.route('/search', methods=['POST'])
def search():
    query_file = request.files['query_image']
    
    # Save temporarily
    with tempfile.NamedTemporaryFile() as tmp:
        query_file.save(tmp.name)
        query_embedding = AdvancedEmbeddingService.generate_embedding(tmp.name)
    
    # Search FAISS
    distances, indices = faiss_service.search_vector(query_embedding, k=5)
    
    # Get results
    mapping = db.get_faiss_to_item_mapping()
    results = [mapping[int(idx)] for idx in indices if idx in mapping]
    
    return jsonify(results)
```

#### Pattern 3: Batch rebuild
```python
# In build_advanced_index.py
def rebuild():
    faiss_service.reset_index()
    
    for image_path in all_images:
        embedding = AdvancedEmbeddingService.generate_embedding(image_path)
        idx = faiss_service.add_vector(embedding)
        db.insert_embedding(image_id, item_id, idx)
    
    faiss_service.save_index()
```

---

### Error Handling

```python
from services.advanced_embedding import AdvancedEmbeddingService

try:
    embedding = AdvancedEmbeddingService.generate_embedding(image_path)
    if embedding is None:
        logger.error("Failed to generate embedding")
        return "Embedding generation failed"
except Exception as e:
    logger.error(f"Error: {e}")
    return f"Error: {str(e)}"

# Common errors:
# - Image not found: FileNotFoundError
# - Corrupt image: PIL error
# - Out of memory: CUDA error (reduce batch size)
# - Model not downloaded: ConnectionError (ensure internet)
```

---

### Performance Tips

```python
# 1. Batch processing (5x faster)
embeddings = AdvancedEmbeddingService.generate_batch_embeddings(image_list)

# 2. Use GPU if available
import torch
if torch.cuda.is_available():
    print("GPU acceleration enabled")

# 3. Pre-initialize models
get_clip_model()  # Load once at startup
get_faiss_service()  # Initialize FAISS

# 4. Tune batch size for your GPU
# More VRAM: increase to 64
# Less VRAM: decrease to 8
AdvancedEmbeddingConfig.BATCH_SIZE = 32
```

---

### Debugging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Check device
import torch
print(f"Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")

# Check FAISS index
info = faiss_service.get_index_info()
print(f"Vectors in index: {info['ntotal']}")
print(f"Index type: {info['type']}")

# Check vector dimension
embedding = AdvancedEmbeddingService.generate_embedding(image_path)
print(f"Embedding shape: {embedding.shape}")
print(f"L2 norm: {np.linalg.norm(embedding)}")
```

---

### Advanced Customization

```python
# Custom feature weights
import services.advanced_embedding as ae

# Modify config class
ae.AdvancedEmbeddingConfig.WEIGHT_CLIP = 0.50
ae.AdvancedEmbeddingConfig.WEIGHT_COLOR = 0.50
# Sum should = 1.0

# Custom image preprocessing
def custom_preprocess(img_cv):
    # Your preprocessing here
    return processed_img

# Then use it in extract functions
```

---

**For more examples, see:**
- `test_advanced_embedding.py` - Unit tests
- `build_advanced_index.py` - Index building
- `app.py` - Integration in Flask routes
- `ADVANCED_EMBEDDING_GUIDE.md` - Full documentation
