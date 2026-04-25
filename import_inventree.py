"""
Inventree Batch Import Tool
Mengambil produk dari Inventree, menyimpan ke uploads/,
menghasilkan embeddings, dan memasukkan ke database + FAISS index.

PENTING: Script ini HANYA mengimpor produk BARU yang BELUM ada di database.
         Produk yang sudah di-embed tidak akan diproses ulang.

Usage:
    python import_inventree.py                      # Import produk baru dari Inventree
    python import_inventree.py --limit 50           # Import maks 50 produk baru
    python import_inventree.py --part-id 123        # Import satu produk (skip jika sudah ada)
    python import_inventree.py --re-embed           # Re-embed semua produk yang sudah ada
    python import_inventree.py --re-embed-all       # Re-embed ulang semua dari awal
"""

import os
import sys
import time
import argparse
import logging
import tempfile
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from tqdm import tqdm
from PIL import Image

# ── project root ──────────────────────────────────────────────────────────────
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import config
from models.db import db
from services.advanced_embedding import AdvancedEmbeddingService
from services.advanced_search import get_faiss_service
from services.inventree_api import get_inventree_service

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("import_inventree.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Helper: Download image from URL
# ══════════════════════════════════════════════════════════════════════════════

def download_image(url: str, save_path: Path, session: requests.Session) -> bool:
    """Download gambar dari URL dan simpan ke disk."""
    try:
        resp = session.get(url, timeout=15, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type:
            logger.warning(f"⚠️  Bukan gambar (content-type={content_type}): {url}")
            return False

        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # Validasi file
        img = Image.open(save_path).convert("RGB")
        img.close()
        return True

    except Exception as e:
        logger.warning(f"⚠️  Gagal download {url}: {e}")
        if save_path.exists():
            save_path.unlink()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# DB helpers
# ══════════════════════════════════════════════════════════════════════════════

def get_all_imported_item_ids() -> set:
    """
    Ambil semua item_id yang sudah ada di database (sudah di-import sebelumnya).
    Digunakan untuk skip produk existing.
    """
    try:
        items = db.get_all_items()
        return set(str(i) for i in items)
    except Exception as e:
        logger.warning(f"⚠️  Could not fetch existing items: {e}")
        return set()


def item_already_imported(item_id: str, existing_ids: set) -> bool:
    """Cek apakah item sudah pernah diimport (menggunakan cached set)."""
    return str(item_id) in existing_ids


def get_existing_images_for_item(item_id: str) -> List[Dict]:
    """Ambil semua gambar yang sudah ada di DB untuk item tertentu."""
    try:
        return db.get_item_details(item_id)
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Core: Re-embed all images of a product
# ══════════════════════════════════════════════════════════════════════════════

def re_embed_product(item_id: str, faiss_service) -> int:
    """Re-embed semua gambar produk dari disk. Return jumlah yang berhasil."""
    logger.info(f"🔄 Re-embedding produk: {item_id}")

    existing_images = get_existing_images_for_item(item_id)
    if not existing_images:
        logger.warning(f"⚠️  Tidak ada data gambar di DB untuk {item_id}")
        return 0

    valid_paths = []
    for rec in existing_images:
        raw_path = rec.get("file_path", "")
        p = Path(raw_path)
        if not p.is_absolute():
            p = project_root / raw_path
        if p.exists():
            valid_paths.append((rec["id"], p))
        else:
            logger.warning(f"⚠️  File tidak ditemukan: {p}")

    if not valid_paths:
        return 0

    embedded = 0
    for image_id, file_path in valid_paths:
        try:
            emb = AdvancedEmbeddingService.generate_embedding(str(file_path))
            if emb is None:
                continue
            faiss_idx = faiss_service.add_vector(emb)
            db.insert_embedding(image_id, item_id, int(faiss_idx))
            embedded += 1
        except Exception as e:
            logger.warning(f"⚠️  Error embed {file_path}: {e}")

    logger.info(f"   ✅ {embedded}/{len(valid_paths)} gambar di-embed untuk {item_id}")
    return embedded


# ══════════════════════════════════════════════════════════════════════════════
# Core: Import single NEW product from Inventree
# ══════════════════════════════════════════════════════════════════════════════

def import_new_product(
    part: Dict,
    inventree_svc,
    faiss_service,
    session: requests.Session = None,
) -> Dict:
    """
    Import satu produk BARU dari Inventree.
    Hanya dipanggil untuk produk yang belum ada di database.

    Return dict statistik.
    """
    part_id   = str(part.get("pk") or part.get("id", ""))
    part_name = part.get("name", "Unknown")

    result = {
        "item_id":          part_id,
        "name":             part_name,
        "status":           "error",
        "images_downloaded": 0,
        "images_embedded":  0,
        "error":            None,
    }

    if not part_id:
        result["error"] = "part_id kosong"
        return result

    # ── Ambil gambar dari Inventree ───────────────────────────────────────────
    success, images, error = inventree_svc.get_part_images(int(part_id))

    if not success or not images:
        # Fallback ke image field di detail endpoint
        ok, part_detail, _ = inventree_svc.get_part_by_id(int(part_id))
        if ok and part_detail and part_detail.get("image"):
            img_url = part_detail["image"]
            if not img_url.startswith("http"):
                img_url = f"{inventree_svc.base_url}{img_url}"
            images = [{"image": img_url, "thumbnail": img_url}]
        else:
            logger.info(f"ℹ️  Tidak ada gambar: [{part_id}] {part_name}")
            result["status"] = "no_image"
            return result

    # ── Download gambar ───────────────────────────────────────────────────────
    item_dir = config.UPLOAD_DIR / part_id
    item_dir.mkdir(parents=True, exist_ok=True)

    new_image_ids = []  # (image_id, file_path)
    downloaded    = 0
    angle_idx     = 1

    for img_info in images:
        img_url = img_info.get("image") or img_info.get("url", "")
        if not img_url:
            continue
        if not img_url.startswith("http"):
            img_url = f"{inventree_svc.base_url}{img_url}"

        angle     = f"id_{angle_idx}"
        save_path = item_dir / f"{angle}.jpg"

        _session = session or inventree_svc.session
        ok = download_image(img_url, save_path, _session)
        if ok:
            downloaded += 1
            relative_path = f"uploads/{part_id}/{angle}.jpg"
            try:
                image_id = db.insert_image(part_id, relative_path, angle)
                new_image_ids.append((image_id, save_path))
                logger.debug(f"   ✓ Download & DB insert: {angle} [{image_id}]")
            except Exception as e:
                logger.warning(f"⚠️  DB insert gagal untuk {angle}: {e}")
        angle_idx += 1

    result["images_downloaded"] = downloaded

    if downloaded == 0:
        result["status"] = "no_image"
        return result

    # ── Embed gambar baru ─────────────────────────────────────────────────────
    embedded = 0
    for image_id, file_path in new_image_ids:
        try:
            emb = AdvancedEmbeddingService.generate_embedding(str(file_path))
            if emb is None:
                logger.warning(f"⚠️  Embedding gagal: {file_path}")
                continue
            faiss_idx = faiss_service.add_vector(emb)
            db.insert_embedding(image_id, part_id, int(faiss_idx))
            embedded += 1
        except Exception as e:
            logger.warning(f"⚠️  Error embed {file_path}: {e}")

    result["images_embedded"] = embedded
    result["status"]          = "imported"

    logger.info(f"✅ Imported [{part_id}] {part_name}: "
                f"{downloaded} gambar, {embedded} di-embed")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Main import function — ONLY NEW products
# ══════════════════════════════════════════════════════════════════════════════

def run_import(
    limit: int = None,
    part_ids: List[int] = None,
    re_embed: bool = False,
    workers: int = 1,
):
    """
    Import hanya produk BARU dari Inventree (yang belum ada di database).
    Produk yang sudah ada di database akan di-skip otomatis.

    Jika --re-embed diberikan, produk yang sudah ada akan di-embed ulang,
    sedangkan produk baru tetap di-import secara normal.
    """
    print("\n" + "═" * 65)
    print("  🏭  Inventree Batch Import Tool  —  New Products Only")
    print("═" * 65)

    # ── Inisialisasi services ─────────────────────────────────────────────────
    logger.info("⚙️  Menginisialisasi services...")

    inventree_svc = get_inventree_service(
        config.INVENTREE_URL,
        config.INVENTREE_USERNAME,
        config.INVENTREE_PASSWORD,
    )
    if inventree_svc is None:
        logger.error("❌ Inventree service tidak tersedia. Periksa konfigurasi .env")
        sys.exit(1)

    try:
        db.connect()
        db.init_tables()
    except Exception as e:
        logger.error(f"❌ Database tidak tersedia: {e}")
        sys.exit(1)

    faiss_service = get_faiss_service()

    # ── Cache existing item IDs ───────────────────────────────────────────────
    existing_ids = get_all_imported_item_ids()
    logger.info(f"📦 {len(existing_ids)} produk sudah ada di database (akan di-skip)")

    # ── Ambil daftar produk dari Inventree ────────────────────────────────────
    if part_ids:
        logger.info(f"📋 Mode: import spesifik {len(part_ids)} part(s)")
        all_parts = []
        for pid in part_ids:
            ok, part, err = inventree_svc.get_part_by_id(pid)
            if ok and part:
                all_parts.append(part)
            else:
                logger.warning(f"⚠️  Part {pid} tidak ditemukan: {err}")
    else:
        logger.info("📋 Mengambil semua produk dari Inventree...")
        fetch_limit = limit if limit else 10000
        ok, all_parts, err = inventree_svc.get_all_parts(limit=fetch_limit)
        if not ok:
            logger.error(f"❌ Gagal mengambil produk: {err}")
            sys.exit(1)

    # ── Pisahkan new vs existing ──────────────────────────────────────────────
    new_parts      = []
    existing_parts = []

    for p in all_parts:
        pid = str(p.get("pk") or p.get("id", ""))
        if item_already_imported(pid, existing_ids):
            existing_parts.append(p)
        else:
            new_parts.append(p)

    # Apply limit only to new parts
    if limit and not part_ids:
        new_parts = new_parts[:limit]

    total_new      = len(new_parts)
    total_existing = len(existing_parts)

    print(f"\n  Produk di Inventree   : {len(all_parts)}")
    print(f"  ✨ Produk BARU        : {total_new}  (akan diimport)")
    print(f"  ⏭️  Produk existing    : {total_existing}  (di-skip)")
    if re_embed:
        print(f"  🔄 Re-embed existing  : Ya (--re-embed aktif)")
    print(f"  Workers               : {workers}")
    print(f"  Inventree             : {config.INVENTREE_URL}")
    print()

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats = {
        "imported":         0,
        "re_embedded":      0,
        "skipped":          0,
        "no_image":         0,
        "error":            0,
        "total_downloaded": 0,
        "total_embedded":   0,
    }

    # ── 1. Import NEW products ─────────────────────────────────────────────────
    if total_new > 0:
        print(f"─── Importing {total_new} new product(s) ───")

        def process_new(part):
            try:
                return import_new_product(part, inventree_svc, faiss_service)
            except Exception as e:
                pid = str(part.get("pk") or part.get("id", "?"))
                logger.error(f"❌ Error pada part {pid}: {e}")
                return {
                    "item_id": pid, "name": part.get("name", "?"),
                    "status": "error", "images_downloaded": 0,
                    "images_embedded": 0, "error": str(e),
                }

        if workers <= 1:
            for part in tqdm(new_parts, desc="Importing new", unit="part"):
                res = process_new(part)
                _update_stats(stats, res)
                if stats["imported"] % 50 == 0:
                    try: faiss_service.save_index()
                    except Exception: pass
        else:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(process_new, p): p for p in new_parts}
                for fut in tqdm(as_completed(futures), total=total_new,
                                desc="Importing new", unit="part"):
                    res = fut.result()
                    _update_stats(stats, res)
    else:
        print("ℹ️  Tidak ada produk baru untuk diimport.\n")

    # ── 2. Re-embed existing products (optional) ───────────────────────────────
    if re_embed and total_existing > 0:
        print(f"\n─── Re-embedding {total_existing} existing product(s) ───")
        for part in tqdm(existing_parts, desc="Re-embedding existing", unit="part"):
            pid = str(part.get("pk") or part.get("id", ""))
            try:
                n = re_embed_product(pid, faiss_service)
                stats["re_embedded"] += 1
                stats["total_embedded"] += n
            except Exception as e:
                logger.error(f"❌ Re-embed error {pid}: {e}")
                stats["error"] += 1
    elif total_existing > 0:
        stats["skipped"] = total_existing

    # ── Save FAISS index ──────────────────────────────────────────────────────
    logger.info("💾 Menyimpan FAISS index ke disk...")
    faiss_service.save_index()

    # ── Summary ───────────────────────────────────────────────────────────────
    _print_summary(stats, total_new, total_existing)

    db.disconnect()


def _update_stats(stats: Dict, res: Dict):
    status = res.get("status", "error")
    if status == "imported":
        stats["imported"] += 1
    elif status == "no_image":
        stats["no_image"] += 1
    elif status == "error":
        stats["error"] += 1
    stats["total_downloaded"] += res.get("images_downloaded", 0)
    stats["total_embedded"]   += res.get("images_embedded",   0)


def _print_summary(stats: Dict, total_new: int, total_existing: int):
    print("\n" + "═" * 65)
    print("  📊  RINGKASAN IMPORT")
    print("═" * 65)
    print(f"  ✨ Produk baru diimport     : {stats['imported']}")
    print(f"  🖼️  Tidak ada gambar         : {stats['no_image']}")
    print(f"  ❌ Error                    : {stats['error']}")
    print(f"  ⏭️  Existing (di-skip)       : {stats['skipped']}")
    print(f"  🔄 Existing (re-embedded)   : {stats['re_embedded']}")
    print(f"  ─────────────────────────────────────────────")
    print(f"  📥 Total gambar didownload  : {stats['total_downloaded']}")
    print(f"  🧠 Total gambar di-embed    : {stats['total_embedded']}")
    print("═" * 65)
    print()


# ══════════════════════════════════════════════════════════════════════════════
# Re-embed ALL existing products
# ══════════════════════════════════════════════════════════════════════════════

def run_re_embed_all():
    """Re-embed ulang semua produk yang sudah ada di database."""
    print("\n" + "═" * 65)
    print("  🔄  Re-Embed Semua Produk")
    print("═" * 65)

    try:
        db.connect()
    except Exception as e:
        logger.error(f"❌ Database: {e}")
        sys.exit(1)

    faiss_service = get_faiss_service()
    faiss_service.reset_index()

    all_items = db.get_all_items()
    logger.info(f"📦 {len(all_items)} produk ditemukan di database")

    total_embedded = 0
    for item_id in tqdm(all_items, desc="Re-embedding", unit="product"):
        n = re_embed_product(item_id, faiss_service)
        total_embedded += n

    faiss_service.save_index()

    print(f"\n  ✅ Re-embed selesai: {total_embedded} gambar di-embed ulang")
    print(f"  📁 FAISS index: {faiss_service.index_path}")
    print("═" * 65 + "\n")

    db.disconnect()


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Inventree Batch Import Tool — hanya produk baru",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python import_inventree.py                      Import semua produk BARU
  python import_inventree.py --limit 100          Import maks 100 produk baru
  python import_inventree.py --part-id 42 55 99   Import produk ID 42, 55, 99 (skip jika sudah ada)
  python import_inventree.py --re-embed           Import baru + re-embed ulang yang sudah ada
  python import_inventree.py --re-embed-all       Re-embed ulang SEMUA produk di DB (tanpa import)
        """,
    )

    parser.add_argument(
        "--limit", type=int, default=None,
        help="Batasi jumlah produk BARU yang diimport"
    )
    parser.add_argument(
        "--part-id", nargs="+", type=int, dest="part_ids", default=None,
        help="Import produk tertentu berdasarkan ID Inventree (skip jika sudah ada)"
    )
    parser.add_argument(
        "--re-embed", action="store_true",
        help="Selain import produk baru, re-embed juga produk yang sudah ada"
    )
    parser.add_argument(
        "--re-embed-all", action="store_true",
        help="Re-embed ulang semua produk yang sudah ada di database (tanpa import)"
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Jumlah worker parallel (default: 1, sequential)"
    )

    args = parser.parse_args()

    if args.re_embed_all:
        run_re_embed_all()
    else:
        run_import(
            limit=args.limit,
            part_ids=args.part_ids,
            re_embed=args.re_embed,
            workers=args.workers,
        )


if __name__ == "__main__":
    main()