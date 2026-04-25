"""
Image-Based Product Search System
Main Flask application with routes for upload and search functionality
Uses advanced embeddings (CLIP + traditional features) for superior search quality
"""
from flask import Flask, render_template, request, redirect, url_for, send_file
import os
import logging
from datetime import datetime

# Import configurations and services
import config
from models.db import db
from pathlib import Path

# Use advanced embedding and search services (NEW)
from services.advanced_embedding import AdvancedEmbeddingService
from services.advanced_search import get_faiss_service
# Fallback to old services if advanced not available
try:
    faiss_service = get_faiss_service()
except Exception as e:
    logging.warning(f"Advanced FAISS service failed: {e}, using basic service")
    from services.search import faiss_service

from services.storage import storage_service
from services.inventree_api import get_inventree_service
from utils.helpers import (
    allowed_file, validate_item_id, validate_angle,
    success_response, error_response, format_search_result,
    format_item_details, handle_errors
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_FILE_SIZE
app.config['UPLOAD_FOLDER'] = str(config.UPLOAD_DIR)

# Initialize Inventree service
inventree_service = get_inventree_service(
    config.INVENTREE_URL,
    config.INVENTREE_USERNAME,
    config.INVENTREE_PASSWORD
)

# Initialize database (optional - app can run without it for initial testing)
try:
    db.connect()
    db.init_tables()
except Exception as e:
    logger.warning(f"⚠️  Database not available: {e}")
    logger.warning(f"   App will run in offline mode (embeddings only)")
    logger.warning(f"   To fix: Check PostgreSQL is running and .env has correct credentials")


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Home page with navigation"""
    try:
        # Get statistics
        all_items = db.get_all_items()
        total_images = 0
        for item_id in all_items:
            images = db.get_item_details(item_id)
            total_images += len(images)
        
        faiss_size = faiss_service.get_index_size()
        storage_stats = storage_service.get_storage_stats()
        
        stats = {
            'total_items': len(all_items),
            'total_images': total_images,
            'total_embeddings': faiss_size,
            'storage_mb': storage_stats.get('total_size_mb', 0)
        }
        
        return render_template('index.html', stats=stats)
    except Exception as e:
        return render_template('index.html', error=str(e))


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Upload product images — supports add & re-embed modes."""
 
    if request.method == 'GET':
        return render_template('upload.html')
 
    # ── Ambil data form ───────────────────────────────────────────────────────
    item_id     = request.form.get('item_id', '').strip()
    upload_mode = request.form.get('upload_mode', 'new')   # new | add | re_embed
 
    if not item_id:
        return render_template('upload.html', error='Product ID wajib diisi')
 
    # ── Cek apakah produk sudah ada di DB ─────────────────────────────────────
    existing_images = db.get_item_details(item_id)
    is_existing     = len(existing_images) > 0
    min_required    = 1 if is_existing else 4
 
    # ── Kumpulkan file upload ─────────────────────────────────────────────────
    uploaded_files = []
    if 'product-images' in request.files:
        for f in request.files.getlist('product-images'):
            if f and f.filename:
                if not allowed_file(f.filename):
                    return render_template('upload.html',
                                           error=f'Tipe file tidak diizinkan: {f.filename}')
                uploaded_files.append(f)
 
    if len(uploaded_files) < min_required:
        return render_template('upload.html',
                               error=f'Upload minimal {min_required} gambar '
                                     f'(saat ini {len(uploaded_files)})')
 
    try:
        # ── Tentukan offset angle untuk gambar baru ───────────────────────────
        next_angle_idx = len(existing_images) + 1   # id_1, id_2, ...
 
        new_image_records = []   # (image_id, full_path)
 
        for f in uploaded_files:
            angle = f'id_{next_angle_idx}'
 
            save_result   = storage_service.save_image(f, item_id, angle)
            full_path     = save_result['full_path']
            relative_path = save_result['file_path']
 
            image_id = db.insert_image(item_id, relative_path, angle)
            new_image_records.append((image_id, full_path))
 
            logger.info(f"✓ Saved: {item_id}/{angle} (DB id={image_id})")
            next_angle_idx += 1
 
        # ── Mode: Re-embed semua gambar (lama + baru) ─────────────────────────
        if upload_mode == 're_embed' and is_existing:
            logger.info(f"🔄 Re-embed mode: {item_id}")
 
            # Ambil SEMUA gambar produk dari DB (sudah include yang baru)
            all_images = db.get_item_details(item_id)
 
            valid_paths = []
            for rec in all_images:
                raw_path = rec.get('file_path', '')
                p = Path(raw_path)
                if not p.is_absolute():
                    p = Path(config.BASE_DIR) / raw_path
                if p.exists():
                    valid_paths.append((rec['id'], str(p)))
                else:
                    logger.warning(f"⚠️  File tidak ditemukan: {p}")
 
            for image_id, file_path in valid_paths:
                emb = AdvancedEmbeddingService.generate_embedding(file_path)
                if emb is None:
                    logger.warning(f"⚠️  Embedding gagal: {file_path}")
                    continue
                faiss_idx = faiss_service.add_vector(emb)
                db.insert_embedding(image_id, item_id, int(faiss_idx))
                logger.info(f"✓ Re-embed: {Path(file_path).name} → FAISS[{faiss_idx}]")
 
            faiss_service.save_index()
 
            total_embedded = len(valid_paths)
            msg = (f"Re-embed selesai: {len(uploaded_files)} gambar baru ditambahkan, "
                   f"{total_embedded} gambar total di-embed ulang untuk produk {item_id}.")
 
        # ── Mode: Tambah gambar baru saja ────────────────────────────────────
        else:
            for image_id, full_path in new_image_records:
                emb = AdvancedEmbeddingService.generate_embedding(full_path)
                if emb is None:
                    raise ValueError(f'Embedding gagal untuk {Path(full_path).name}')
                faiss_idx = faiss_service.add_vector(emb)
                db.insert_embedding(image_id, item_id, int(faiss_idx))
                logger.info(f"✓ Embed: {Path(full_path).name} → FAISS[{faiss_idx}]")
 
            faiss_service.save_index()
 
            if is_existing:
                msg = (f"Berhasil menambahkan {len(uploaded_files)} gambar baru "
                       f"untuk produk {item_id}. "
                       f"Total gambar: {len(existing_images) + len(uploaded_files)}.")
            else:
                msg = (f"Berhasil mengupload {len(uploaded_files)} gambar "
                       f"untuk produk baru {item_id}!")
 
        return render_template('upload.html', success=True, message=msg)
 
    except Exception as e:
        logger.error(f"✗ Upload error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('upload.html', error=f'Upload gagal: {str(e)}')

@app.route('/api/search-products', methods=['GET'])
def api_search_products():
    """API endpoint to search products from Inventree by name or SKU"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return {'success': False, 'error': 'Query must be at least 2 characters', 'products': []}
        
        if not inventree_service:
            return {'success': False, 'error': 'Inventree service not available', 'products': []}
        
        # Search products
        success, parts, error = inventree_service.search_parts(query, limit=50)
        
        if not success:
            return {'success': False, 'error': error, 'products': []}
        
        # Format results
        products = inventree_service.format_parts_for_dropdown(parts)
        
        logger.info(f"✓ Product search: '{query}' found {len(products)} results")
        
        return {
            'success': True,
            'error': None,
            'products': products,
            'count': len(products)
        }
        
    except Exception as e:
        logger.error(f"✗ Product search error: {e}")
        return {'success': False, 'error': str(e), 'products': []}


@app.route('/search', methods=['GET', 'POST'])
def search():
    """Search for similar products endpoint"""
    
    if request.method == 'GET':
        # Show search form
        return render_template('search.html')
    
    # POST request - handle search
    try:
        # Check for file
        if 'query_image' not in request.files:
            return render_template('search.html', 
                                 error='No query image provided')
        
        file = request.files['query_image']
        
        if file.filename == '':
            return render_template('search.html', 
                                 error='No image selected')
        
        if not allowed_file(file.filename):
            return render_template('search.html',
                                 error=f'File type not allowed')
        
        # Save query image temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            file.save(tmp.name)
            query_path = tmp.name
        
        print(f"\n🔍 Searching for similar images...")
        
        # Generate advanced embedding for query image
        query_embedding = AdvancedEmbeddingService.generate_embedding(query_path)
        if query_embedding is None:
            raise ValueError("Failed to generate query embedding")
        print(f"✓ Generated advanced query embedding: shape={query_embedding.shape}")
        
        # Search FAISS index
        k = min(config.SEARCH_TOP_K, faiss_service.get_index_size())
        
        if k == 0:
            return render_template('search.html',
                                 error='No images in database yet')
        
        distances, indices = faiss_service.search_vector(query_embedding, k=k)
        print(f"✓ FAISS search returned {len(indices)} results")
        
        # Get FAISS → item_id mapping
        faiss_mapping = db.get_faiss_to_item_mapping()
        
        # Aggregate results by item_id (voting)
        item_votes = {}
        results_detail = []
        
        for faiss_idx, distance in zip(indices, distances):
            faiss_idx = int(faiss_idx)
            
            if faiss_idx not in faiss_mapping:
                continue
            
            item_id = faiss_mapping[faiss_idx]
            
            # Count votes
            if item_id not in item_votes:
                item_votes[item_id] = {'count': 0, 'min_distance': distance}
            
            item_votes[item_id]['count'] += 1
            item_votes[item_id]['min_distance'] = min(item_votes[item_id]['min_distance'], distance)
            
            results_detail.append({
                'faiss_index': faiss_idx,
                'item_id': item_id,
                'distance': float(distance)
            })
        
        # Sort by vote count and min distance
        sorted_results = sorted(
            item_votes.items(),
            key=lambda x: (-x[1]['count'], x[1]['min_distance'])
        )
        
        # Format results
        search_results = []
        for item_id, vote_info in sorted_results[:5]:
            images = db.get_item_details(item_id)
            
            # Calculate similarity score
            from utils.helpers import format_similarity_score
            similarity = format_similarity_score(vote_info['min_distance'])
            
            # Get product details from Inventree
            product_name = None
            product_sku = None
            image_url = None
            
            if inventree_service:
                success, part, error = inventree_service.get_part_by_id(int(item_id))
                if success and part:
                    product_name = part.get('name', None)
                    product_sku = part.get('keywords', None)
                    # Get product image
                    image_url = inventree_service.get_part_image_url(int(item_id))
                    logger.info(f"✓ Retrieved product details for {item_id}: {product_name} ({product_sku})")
            
            print("image_url", image_url)

            search_results.append({
                'item_id': item_id,
                'product_name': product_name,
                'product_sku': product_sku,
                'similarity_score': similarity,
                'matched_images': vote_info['count'],
                'distance': round(vote_info['min_distance'], 4),
                'image_count': len(images),
                'image_url': image_url
            })
        
        print(f"✓ Found {len(search_results)} matching items")
        
        # Clean up temp file
        try:
            os.remove(query_path)
        except:
            pass
        
        return render_template('search.html',
                             results=search_results,
                             result_count=len(search_results))
    
    except Exception as e:
        print(f"✗ Search error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('search.html', 
                             error=f'Search failed: {str(e)}')


@app.route('/api/product-image/<product_id>')
def api_product_image(product_id):
    """API endpoint to get product image from Inventree"""
    try:
        if not inventree_service:
            return {'success': False, 'error': 'Inventree service not available', 'image_url': None}
        
        # Get product image URL
        image_url = inventree_service.get_part_image_url(int(product_id))
        
        if image_url:
            logger.info(f"✓ Got image URL for product {product_id}")
            return {'success': True, 'image_url': image_url, 'error': None}
        else:
            return {'success': False, 'error': 'No image found', 'image_url': None}
            
    except Exception as e:
        logger.error(f"Error fetching product image: {e}")
        return {'success': False, 'error': str(e), 'image_url': None}


@app.route('/api/items')
def api_items():
    """API: Get all items"""
    try:
        items = db.get_all_items()
        item_data = []
        
        for item_id in items:
            images = db.get_item_details(item_id)
            item_data.append({
                'item_id': item_id,
                'image_count': len(images),
                'images': [
                    {
                        'angle': img['angle'],
                        'file_path': img['file_path']
                    }
                    for img in images
                ]
            })
        
        return success_response(item_data, f"Retrieved {len(item_data)} items")
    except Exception as e:
        return error_response(str(e), 500)


@app.route('/api/item/<item_id>')
def api_item_details(item_id):
    """API: Get details for specific item"""
    try:
        images = db.get_item_details(item_id)
        
        if not images:
            return error_response(f"Item not found: {item_id}", 404)
        
        data = format_item_details(item_id, images)
        return success_response(data)
    except Exception as e:
        return error_response(str(e), 500)


@app.route('/api/stats')
def api_stats():
    """API: Get system statistics"""
    try:
        all_items = db.get_all_items()
        total_images = 0
        
        for item_id in all_items:
            images = db.get_item_details(item_id)
            total_images += len(images)
        
        faiss_size = faiss_service.get_index_size()
        storage_stats = storage_service.get_storage_stats()
        
        stats = {
            'total_items': len(all_items),
            'total_images': total_images,
            'total_embeddings': faiss_size,
            'storage_mb': storage_stats.get('total_size_mb', 0),
            'file_count': storage_stats.get('file_count', 0)
        }
        
        return success_response(stats)
    except Exception as e:
        return error_response(str(e), 500)


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return render_template('error.html', 
                         error='Page not found',
                         status_code=404), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    return render_template('error.html',
                         error='Internal server error',
                         status_code=500), 500


# ==================== APP STARTUP ====================

if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════════════╗
    ║  🎯 Image-Based Product Search System         ║
    ║  Backend: Flask                               ║
    ║  Database: PostgreSQL                         ║
    ║  Vector Search: FAISS                         ║
    ╚════════════════════════════════════════════════╝
    """)
    
    print(f"📁 Upload Directory: {config.UPLOAD_DIR}")
    print(f"📁 Embeddings Directory: {config.EMBEDDING_DIR}")
    print(f"🗄️  Database: {config.DATABASE_URL}")
    
    # Load FAISS index if it exists
    try:
        if config.EMBEDDINGS_INDEX_PATH.exists():
            faiss_service.load_index()
    except Exception as e:
        print(f"⚠ Could not load FAISS index: {e}")
    
    print("\n🚀 Starting Flask application...\n")
    app.run(debug=config.DEBUG, host='0.0.0.0', port=5000)
