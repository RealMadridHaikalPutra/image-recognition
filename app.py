"""
Image-Based Product Search System
Main Flask application with routes for upload and search functionality
Uses advanced embeddings (CLIP + traditional features) for superior search quality
"""
from flask import Flask, render_template, request, redirect, url_for, send_file, abort
import os
import logging
from datetime import datetime
from pathlib import Path

# Import configurations and services
import config
from models.db import db

# Use advanced embedding and search services
from services.advanced_embedding import AdvancedEmbeddingService
from services.advanced_search import get_faiss_service
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

# Initialize database
try:
    db.connect()
    db.init_tables()
except Exception as e:
    logger.warning(f"⚠️  Database not available: {e}")
    logger.warning(f"   App will run in offline mode (embeddings only)")


# ==================== HELPER ====================

def delete_image_record(image_id: int):
    """
    Delete a single image record from DB and its file from disk.
    Also removes associated embedding rows.
    """
    if not db.conn:
        db.connect()
    cur = db.conn.cursor()
    try:
        # Get file path before deleting
        cur.execute("SELECT file_path FROM items_images WHERE id = %s;", (image_id,))
        row = cur.fetchone()
        if row:
            file_path = row[0]
            # Delete embedding rows first (FK cascade may handle this, but be safe)
            cur.execute("DELETE FROM embeddings WHERE image_id = %s;", (image_id,))
            # Delete image record
            cur.execute("DELETE FROM items_images WHERE id = %s;", (image_id,))
            db.conn.commit()
            logger.info(f"✓ Deleted DB record for image_id={image_id}")

            # Delete file from disk
            p = Path(file_path)
            if not p.is_absolute():
                p = config.BASE_DIR / file_path
            if p.exists():
                p.unlink()
                logger.info(f"✓ Deleted file: {p}")
        else:
            db.conn.commit()
    except Exception as e:
        db.conn.rollback()
        logger.error(f"✗ Error deleting image {image_id}: {e}")
        raise
    finally:
        cur.close()


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Home page with navigation"""
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
            'storage_mb': storage_stats.get('total_size_mb', 0)
        }
        return render_template('index.html', stats=stats)
    except Exception as e:
        return render_template('index.html', error=str(e))


# ── Serve uploaded images to the frontend ──────────────────────────────────────
@app.route('/uploads-serve/<path:file_path>')
def serve_uploaded_image(file_path):
    """
    Serve an uploaded image given its relative file_path stored in the DB.
    Example: /uploads-serve/uploads%2FPROD-001%2Fid_1.jpg
    """
    from urllib.parse import unquote
    decoded = unquote(file_path)

    # Build absolute path
    p = Path(decoded)
    if not p.is_absolute():
        p = config.BASE_DIR / decoded

    if not p.exists():
        abort(404)

    # Basic security: must be inside UPLOAD_DIR
    try:
        p.resolve().relative_to(config.UPLOAD_DIR.resolve())
    except ValueError:
        abort(403)

    return send_file(str(p))


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Upload product images — supports add & re-embed modes, with delete before re-embed."""

    if request.method == 'GET':
        return render_template('upload.html')

    # ── Form data ─────────────────────────────────────────────────────────────
    item_id           = request.form.get('item_id', '').strip()
    upload_mode       = request.form.get('upload_mode', 'new')
    delete_ids_raw    = request.form.get('delete_image_ids', '').strip()

    if not item_id:
        return render_template('upload.html', error='Product ID wajib diisi')

    # ── Parse delete IDs ──────────────────────────────────────────────────────
    delete_ids = []
    if delete_ids_raw:
        for raw in delete_ids_raw.split(','):
            raw = raw.strip()
            if raw.isdigit():
                delete_ids.append(int(raw))

    # ── Existing images ────────────────────────────────────────────────────────
    existing_images = db.get_item_details(item_id)
    is_existing     = len(existing_images) > 0
    min_required    = 0 if is_existing else 4

    # ── Uploaded files ─────────────────────────────────────────────────────────
    uploaded_files = []
    if 'product-images' in request.files:
        for f in request.files.getlist('product-images'):
            if f and f.filename:
                if not allowed_file(f.filename):
                    return render_template('upload.html',
                                           error=f'Tipe file tidak diizinkan: {f.filename}')
                uploaded_files.append(f)

    # Validate minimum
    if not is_existing and len(uploaded_files) < min_required:
        return render_template('upload.html',
                               error=f'Upload minimal {min_required} gambar '
                                     f'(saat ini {len(uploaded_files)})')

    # For existing: must have at least some images remaining after delete
    # Validasi untuk existing product (FIX: boleh hanya hapus tanpa upload baru)
    remaining_after_delete = len(existing_images) - len(delete_ids)
    # Validasi untuk existing product (FINAL CLEAN)
    if is_existing:
        # ❗ Tidak boleh sampai 0 gambar TANPA upload baru
        if remaining_after_delete <= 0 and len(uploaded_files) == 0:
            return render_template(
                'upload.html',
                error='Tidak bisa menghapus semua gambar tanpa mengupload gambar baru.'
            )

    # ✅ Tidak ada validasi "harus ada perubahan"
    # Jadi:
    # - delete saja → boleh
    # - upload saja → boleh
    # - tidak ada aksi → juga boleh

    try:
        # ── Step 1: Delete marked images ──────────────────────────────────────
        if delete_ids:
            for img_id in delete_ids:
                try:
                    delete_image_record(img_id)
                    logger.info(f"✓ Deleted image id={img_id}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not delete image {img_id}: {e}")

        # ── Step 2: Save new uploaded files ───────────────────────────────────
        # Re-fetch existing images AFTER deletion to compute next angle index
        existing_after_delete = db.get_item_details(item_id)
        next_angle_idx = len(existing_after_delete) + 1

        new_image_records = []  # (image_id, full_path)

        for f in uploaded_files:
            angle = f'id_{next_angle_idx}'
            save_result   = storage_service.save_image(f, item_id, angle)
            full_path     = save_result['full_path']
            relative_path = save_result['file_path']
            image_id      = db.insert_image(item_id, relative_path, angle)
            new_image_records.append((image_id, full_path))
            logger.info(f"✓ Saved: {item_id}/{angle} (DB id={image_id})")
            next_angle_idx += 1

        # ── Step 3: Re-embed ───────────────────────────────────────────────────
        # Always re-embed ALL remaining images when product already existed
        if upload_mode == 're_embed' and is_existing:
            logger.info(f"🔄 Re-embed mode: {item_id}")

            all_images_now = db.get_item_details(item_id)

            valid_paths = []
            for rec in all_images_now:
                raw_path = rec.get('file_path', '')
                p = Path(raw_path)
                if not p.is_absolute():
                    p = Path(config.BASE_DIR) / raw_path
                if p.exists():
                    valid_paths.append((rec['id'], str(p)))
                else:
                    logger.warning(f"⚠️  File tidak ditemukan: {p}")

            # Clear old embedding entries for this item to avoid duplicates
            _clear_embeddings_for_item(item_id)

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
            _parts = []
            if len(uploaded_files) > 0:
                _parts.append(f"{len(uploaded_files)} gambar baru ditambahkan")
            if delete_ids:
                _parts.append(f"{len(delete_ids)} gambar dihapus")
            _parts.append(f"{total_embedded} gambar total di-embed ulang")
            msg = f"Selesai untuk produk {item_id}: " + ", ".join(_parts) + "."

        # ── New product: embed only new files ─────────────────────────────────
        else:
            for image_id, full_path in new_image_records:
                emb = AdvancedEmbeddingService.generate_embedding(full_path)
                if emb is None:
                    raise ValueError(f'Embedding gagal untuk {Path(full_path).name}')
                faiss_idx = faiss_service.add_vector(emb)
                db.insert_embedding(image_id, item_id, int(faiss_idx))
                logger.info(f"✓ Embed: {Path(full_path).name} → FAISS[{faiss_idx}]")

            faiss_service.save_index()
            msg = (f"Berhasil mengupload {len(uploaded_files)} gambar "
                   f"untuk produk baru {item_id}!")

        return render_template('upload.html', success=True, message=msg)

    except Exception as e:
        logger.error(f"✗ Upload error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('upload.html', error=f'Upload gagal: {str(e)}')


def _clear_embeddings_for_item(item_id: str):
    """Remove all embedding rows for an item (before re-embed)."""
    if not db.conn:
        db.connect()
    cur = db.conn.cursor()
    try:
        cur.execute("DELETE FROM embeddings WHERE item_id = %s;", (item_id,))
        db.conn.commit()
        logger.info(f"✓ Cleared old embeddings for {item_id}")
    except Exception as e:
        db.conn.rollback()
        logger.warning(f"⚠️  Could not clear embeddings: {e}")
    finally:
        cur.close()


@app.route('/api/search-products', methods=['GET'])
def api_search_products():
    """API endpoint to search products from Inventree by name or SKU"""
    try:
        query = request.args.get('q', '').strip()

        if not query or len(query) < 2:
            return {'success': False, 'error': 'Query must be at least 2 characters', 'products': []}

        if not inventree_service:
            return {'success': False, 'error': 'Inventree service not available', 'products': []}

        success, parts, error = inventree_service.search_parts(query, limit=50)

        if not success:
            return {'success': False, 'error': error, 'products': []}

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


@app.route('/api/delete-image/<int:image_id>', methods=['DELETE', 'POST'])
def api_delete_image(image_id):
    """API: Delete a single image record and file"""
    try:
        delete_image_record(image_id)
        return success_response(message=f"Image {image_id} deleted")
    except Exception as e:
        return error_response(str(e), 500)


@app.route('/search', methods=['GET', 'POST'])
def search():
    """Search for similar products endpoint"""

    if request.method == 'GET':
        return render_template('search.html')

    try:
        if 'query_image' not in request.files:
            return render_template('search.html', error='No query image provided')

        file = request.files['query_image']

        if file.filename == '':
            return render_template('search.html', error='No image selected')

        if not allowed_file(file.filename):
            return render_template('search.html', error='File type not allowed')

        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            file.save(tmp.name)
            query_path = tmp.name

        print(f"\n🔍 Searching for similar images...")

        query_embedding = AdvancedEmbeddingService.generate_embedding(query_path)
        if query_embedding is None:
            raise ValueError("Failed to generate query embedding")
        print(f"✓ Generated advanced query embedding: shape={query_embedding.shape}")

        k = min(config.SEARCH_TOP_K, faiss_service.get_index_size())

        if k == 0:
            return render_template('search.html', error='No images in database yet')

        distances, indices = faiss_service.search_vector(query_embedding, k=k)
        print(f"✓ FAISS search returned {len(indices)} results")

        faiss_mapping = db.get_faiss_to_item_mapping()

        item_votes = {}
        for faiss_idx, distance in zip(indices, distances):
            faiss_idx = int(faiss_idx)
            if faiss_idx not in faiss_mapping:
                continue
            item_id = faiss_mapping[faiss_idx]
            if item_id not in item_votes:
                item_votes[item_id] = {'count': 0, 'min_distance': distance}
            item_votes[item_id]['count'] += 1
            item_votes[item_id]['min_distance'] = min(item_votes[item_id]['min_distance'], distance)

        sorted_results = sorted(
            item_votes.items(),
            key=lambda x: (-x[1]['count'], x[1]['min_distance'])
        )

        search_results = []
        for item_id, vote_info in sorted_results[:5]:
            images = db.get_item_details(item_id)

            from utils.helpers import format_similarity_score
            similarity = format_similarity_score(vote_info['min_distance'])

            product_name = None
            product_sku  = None
            image_url    = None

            if inventree_service:
                ok, part, err = inventree_service.get_part_by_id(int(item_id))
                if ok and part:
                    product_name = part.get('name', None)
                    product_sku  = part.get('keywords', None)
                    image_url    = inventree_service.get_part_image_url(int(item_id))

            search_results.append({
                'item_id':          item_id,
                'product_name':     product_name,
                'product_sku':      product_sku,
                'similarity_score': similarity,
                'matched_images':   vote_info['count'],
                'distance':         round(vote_info['min_distance'], 4),
                'image_count':      len(images),
                'image_url':        image_url
            })

        print(f"✓ Found {len(search_results)} matching items")

        try:
            os.remove(query_path)
        except Exception:
            pass

        return render_template('search.html',
                               results=search_results,
                               result_count=len(search_results))

    except Exception as e:
        print(f"✗ Search error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('search.html', error=f'Search failed: {str(e)}')


@app.route('/api/product-image/<product_id>')
def api_product_image(product_id):
    """API endpoint to get product image from Inventree"""
    try:
        if not inventree_service:
            return {'success': False, 'error': 'Inventree service not available', 'image_url': None}
        image_url = inventree_service.get_part_image_url(int(product_id))
        if image_url:
            return {'success': True, 'image_url': image_url, 'error': None}
        return {'success': False, 'error': 'No image found', 'image_url': None}
    except Exception as e:
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
                'item_id':     item_id,
                'image_count': len(images),
                'images': [
                    {'angle': img['angle'], 'file_path': img['file_path']}
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
        if images is None:
            return error_response(f"Item not found: {item_id}", 404)

        # Kalau kosong, tetap return sukses
        data = format_item_details(item_id, images)
        return success_response(data)
    except Exception as e:
        return error_response(str(e), 500)


@app.route('/api/stats')
def api_stats():
    """API: Get system statistics"""
    try:
        all_items    = db.get_all_items()
        total_images = sum(len(db.get_item_details(i)) for i in all_items)
        faiss_size   = faiss_service.get_index_size()
        storage_stats = storage_service.get_storage_stats()

        stats = {
            'total_items':      len(all_items),
            'total_images':     total_images,
            'total_embeddings': faiss_size,
            'storage_mb':       storage_stats.get('total_size_mb', 0),
            'file_count':       storage_stats.get('file_count', 0)
        }
        return success_response(stats)
    except Exception as e:
        return error_response(str(e), 500)


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='Page not found', status_code=404), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html', error='Internal server error', status_code=500), 500


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

    try:
        if config.EMBEDDINGS_INDEX_PATH.exists():
            faiss_service.load_index()
    except Exception as e:
        print(f"⚠ Could not load FAISS index: {e}")

    print("\n🚀 Starting Flask application...\n")
    app.run(debug=config.DEBUG, host='0.0.0.0', port=5000)