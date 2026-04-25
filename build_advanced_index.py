"""
Advanced Database Builder
Builds FAISS index from images in the uploads folder using advanced embeddings.

Usage:
    python build_advanced_index.py
"""

import os
import sys
from pathlib import Path
from typing import List, Dict
import pickle
import logging

import numpy as np
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import from project
import config
from models.db import db
from services.advanced_embedding import (
    AdvancedEmbeddingService,
    load_and_preprocess,
    extract_traditional_features,
    extract_clip_embedding,
    combine_features
)
from services.advanced_search import get_faiss_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def build_advanced_index_from_database():
    """
    Build FAISS index from images already in the database.
    Reads from items_images table and generates embeddings.
    """
    
    print("\n" + "="*60)
    print("🏗️  Building Advanced FAISS Index from Database")
    print("="*60)
    
    # Connect to database
    db.connect()
    
    # Get all items
    all_items = db.get_all_items()
    logger.info(f"📦 Found {len(all_items)} items in database")
    
    if len(all_items) == 0:
        logger.warning("⚠️  No items in database. Upload images first!")
        db.disconnect()
        return
    
    # Get FAISS service
    faiss_service = get_faiss_service()
    faiss_service.reset_index()
    
    # Collect all image records
    all_images = []
    for item_id in all_items:
        images = db.get_item_details(item_id)
        all_images.extend(images)
    
    total_images = len(all_images)
    logger.info(f"🖼️  Found {total_images} total images")
    
    # Build mapping from FAISS index to item_id
    # We'll need to update embeddings table with new FAISS indices
    
    print("\n📸 Step 1/3: Load and preprocess images...")
    valid_records = []
    imgs_cv = []
    imgs_pil = []
    
    def _load_image(record):
        """Load and preprocess single image"""
        try:
            local_path = Path(record['file_path'])
            # Convert from relative path if needed
            if not local_path.is_absolute():
                local_path = config.UPLOAD_DIR.parent / local_path
            
            if not local_path.exists():
                return None, None
            
            img_cv = load_and_preprocess(str(local_path))
            if img_cv is None:
                return None, None
            
            from PIL import Image
            img_pil = Image.fromarray(img_cv).convert("RGB")
            return img_cv, img_pil
        except Exception as e:
            logger.warning(f"⚠️  Failed to load {record['file_path']}: {e}")
            return None, None
    
    # Parallel loading
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_load_image, rec): i 
                  for i, rec in enumerate(all_images)}
        
        for fut in tqdm(as_completed(futures), total=total_images, desc="Loading"):
            i = futures[fut]
            img_cv, img_pil = fut.result()
            if img_cv is not None:
                valid_records.append(all_images[i])
                imgs_cv.append(img_cv)
                imgs_pil.append(img_pil)
    
    n_valid = len(valid_records)
    logger.info(f"✅ {n_valid}/{total_images} images loaded")
    
    if n_valid == 0:
        logger.error("❌ No valid images found!")
        db.disconnect()
        return
    
    # Step 2: Extract CLIP embeddings in batch
    print("\n🤖 Step 2/3: Extract CLIP embeddings (batch GPU)...")
    from services.advanced_embedding import extract_clip_batch
    clip_embs = extract_clip_batch(imgs_pil)
    logger.info(f"✅ CLIP embeddings: {clip_embs.shape}")
    
    # Step 3: Extract traditional features (parallel CPU)
    print("\n🎨 Step 3/3: Extract traditional features (parallel CPU)...")
    trad_feats = [None] * n_valid
    
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(extract_traditional_features, img): i
                  for i, img in enumerate(imgs_cv)}
        
        for fut in tqdm(as_completed(futures), total=n_valid, desc="Trad. Feats"):
            idx = futures[fut]
            trad_feats[idx] = fut.result()
    
    # Combine features and build index
    print("\n⚡ Combining features and building index...")
    faiss_indices = []
    
    for i, (clip_emb, trad_feat) in enumerate(
        tqdm(zip(clip_embs, trad_feats), total=n_valid, desc="Combining")
    ):
        color_v, bright_v, tex_v, edge_v, dominant_v = trad_feat
        final_vec = combine_features(
            clip_emb, color_v, bright_v, tex_v, edge_v, dominant_v
        )
        
        # Add to FAISS and get index
        idx = faiss_service.add_vector(final_vec)
        faiss_indices.append(idx)
    
    # Save FAISS index
    faiss_service.save_index()
    
    # Update database with new FAISS indices
    # Clear old embeddings
    print("\n📝 Updating database with new indices...")
    
    # Note: You might want to truncate embeddings table first
    # For now, we'll just add new records
    for record, faiss_idx in tqdm(zip(valid_records, faiss_indices),
                                  total=len(valid_records), desc="Updating DB"):
        try:
            db.insert_embedding(
                record['id'],
                record['item_id'],
                int(faiss_idx)
            )
        except Exception as e:
            logger.warning(f"⚠️  Failed to update {record['id']}: {e}")
    
    # Print summary
    print("\n" + "="*60)
    print(f"✅ SUCCESS — {n_valid} images indexed")
    print(f"📁 FAISS Index: {faiss_service.index_path}")
    print(f"📊 Index Info: {faiss_service.get_index_info()}")
    print("="*60 + "\n")
    
    db.disconnect()


def rebuild_index_incremental():
    """
    Rebuild index incrementally from embeddings table.
    Useful if database already has embeddings but FAISS is lost/corrupted.
    """
    print("\n" + "="*60)
    print("🔄 Rebuilding FAISS Index (Incremental)")
    print("="*60)
    
    db.connect()
    
    # Get FAISS service
    faiss_service = get_faiss_service()
    faiss_service.reset_index()
    
    # Get all embeddings from database
    # (This assumes embeddings table has a column with embedding vectors,
    # which the current schema doesn't have — would need DB migration)
    
    logger.warning("⚠️  Note: Current schema doesn't store embeddings in DB")
    logger.warning("       Would need to store embedding vectors in database")
    logger.info("💡 Run build_advanced_index_from_database() instead")
    
    db.disconnect()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build advanced FAISS index")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild from scratch (default)"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Rebuild incrementally from DB"
    )
    
    args = parser.parse_args()
    
    if args.incremental:
        rebuild_index_incremental()
    else:
        build_advanced_index_from_database()
