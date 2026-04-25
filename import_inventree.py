"""
Inventree Batch Import Tool
Mengambil semua produk dan gambar dari Inventree, menyimpan ke uploads/,
menghasilkan embeddings, dan memasukkan ke database + FAISS index.

Usage:
    python import_inventree.py                      # Import semua produk
    python import_inventree.py --limit 50           # Import 50 produk pertama
    python import_inventree.py --part-id 123        # Import satu produk
    python import_inventree.py --skip-existing      # Skip produk yang sudah ada
    python import_inventree.py --re-embed           # Re-embed semua produk
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
    """
    Download gambar dari URL dan simpan ke disk.
    Returns True jika berhasil, False jika gagal.
    """
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

        # Validasi file bisa dibuka sebagai gambar
        img = Image.open(save_path).convert("RGB")
        img.close()
        return True

    except Exception as e:
        logger.warning(f"⚠️  Gagal download {url}: {e}")
        if save_path.exists():
            save_path.unlink()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Core: Check existing product in DB
# ══════════════════════════════════════════════════════════════════════════════

def get_existing_images_for_item(item_id: str) -> List[Dict]:
    """Ambil semua gambar yang sudah ada di DB untuk item tertentu."""
    try:
        return db.get_item_details(item_id)
    except Exception:
        return []


def item_already_imported(item_id: str) -> bool:
    """Cek apakah item sudah pernah diimport."""
    images = get_existing_images_for_item(item_id)
    return len(images) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Core: Re-embed all images of a product
# ══════════════════════════════════════════════════════════════════════════════

def re_embed_product(item_id: str, faiss_service) -> int:
    """
    Hapus embedding lama untuk item_id dari FAISS, lalu generate ulang
    dari SEMUA file gambar yang ada di disk untuk item tersebut.
    Kembalikan jumlah gambar yang berhasil di-embed.
    """
    logger.info(f"🔄 Re-embedding produk: {item_id}")

    # Ambil semua record gambar dari DB
    existing_images = get_existing_images_for_item(item_id)
    if not existing_images:
        logger.warning(f"⚠️  Tidak ada data gambar di DB untuk {item_id}")
        return 0

    # Kumpulkan path file yang benar-benar ada di disk
    valid_paths = []
    for rec in existing_images:
        raw_path = rec.get("file_path", "")
        # Normalisasi path (bisa relative atau absolute)
        p = Path(raw_path)
        if not p.is_absolute():
            p = project_root / raw_path
        if p.exists():
            valid_paths.append((rec["id"], p))
        else:
            logger.warning(f"⚠️  File tidak ditemukan: {p}")

    if not valid_paths:
        logger.warning(f"⚠️  Tidak ada file valid untuk {item_id}")
        return 0

    # Generate embedding untuk setiap gambar dan tambahkan ke FAISS
    embedded = 0
    for image_id, file_path in valid_paths:
        try:
            emb = AdvancedEmbeddingService.generate_embedding(str(file_path))
            if emb is None:
                logger.warning(f"⚠️  Embedding gagal untuk {file_path}")
                continue

            faiss_idx = faiss_service.add_vector(emb)
            db.insert_embedding(image_id, item_id, int(faiss_idx))
            embedded += 1
            logger.debug(f"   ✓ {file_path.name} → FAISS[{faiss_idx}]")

        except Exception as e:
            logger.warning(f"⚠️  Error embed {file_path}: {e}")

    logger.info(f"   ✅ {embedded}/{len(valid_paths)} gambar di-embed ulang untuk {item_id}")
    return embedded


# ══════════════════════════════════════════════════════════════════════════════
# Core: Import single product from Inventree
# ══════════════════════════════════════════════════════════════════════════════

def import_single_product(
    part: Dict,
    inventree_svc,
    faiss_service,
    skip_existing: bool = False,
    re_embed: bool = False,
    session: requests.Session = None,
) -> Dict:
    """
    Import satu produk dari Inventree:
    1. Download gambar → uploads/{item_id}/id_{n}.jpg
    2. Insert metadata ke DB
    3. Generate embedding
    4. Tambahkan ke FAISS

    Jika produk sudah ada:
    - skip_existing=True  → langsung skip
    - re_embed=True       → tambah gambar baru + re-embed semua
    - default             → tambah gambar baru saja, tanpa re-embed

    Return dict statistik.
    """
    part_id = str(part.get("pk") or part.get("id", ""))
    part_name = part.get("name", "Unknown")

    result = {
        "item_id": part_id,
        "name": part_name,
        "status": "skip",
        "images_downloaded": 0,
        "images_embedded": 0,
        "error": None,
    }

    if not part_id:
        result["error"] = "part_id kosong"
        return result

    # ── Cek apakah sudah ada ──────────────────────────────────────────────────
    already_exists = item_already_imported(part_id)

    if already_exists and skip_existing:
        logger.info(f"⏭️  Skip (sudah ada): [{part_id}] {part_name}")
        result["status"] = "skipped"
        return result

    # ── Ambil gambar dari Inventree ───────────────────────────────────────────
    success, images, error = inventree_svc.get_part_images(int(part_id))

    if not success or not images:
        # Coba ambil via get_part_by_id (fallback)
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

    # ── Tentukan offset index gambar baru ────────────────────────────────────
    existing_images = get_existing_images_for_item(part_id)
    existing_count = len(existing_images)
    next_angle_idx = existing_count + 1  # id_1, id_2, ...

    # ── Download gambar ───────────────────────────────────────────────────────
    item_dir = config.UPLOAD_DIR / part_id
    item_dir.mkdir(parents=True, exist_ok=True)

    new_image_ids = []  # (image_id, file_path)
    downloaded = 0

    for img_info in images:
        img_url = img_info.get("image") or img_info.get("url", "")
        if not img_url:
            continue
        if not img_url.startswith("http"):
            img_url = f"{inventree_svc.base_url}{img_url}"

        angle = f"id_{next_angle_idx}"
        save_path = item_dir / f"{angle}.jpg"

        # Skip kalau file sudah ada (misal sudah didownload sebelumnya)
        if save_path.exists():
            logger.debug(f"   File sudah ada, skip download: {save_path}")
            next_angle_idx += 1
            continue

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
            next_angle_idx += 1

    result["images_downloaded"] = downloaded

    # ── Embedding ─────────────────────────────────────────────────────────────
    if already_exists and re_embed:
        # Re-embed SEMUA gambar (lama + baru)
        embedded = re_embed_product(part_id, faiss_service)
        result["images_embedded"] = embedded
        result["status"] = "re_embedded"
    else:
        # Embed hanya gambar baru yang baru didownload
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
        result["status"] = "imported" if downloaded > 0 else "no_new_image"

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Main import function
# ══════════════════════════════════════════════════════════════════════════════

def run_import(
    limit: int = None,
    part_ids: List[int] = None,
    skip_existing: bool = False,
    re_embed: bool = False,
    workers: int = 1,
):
    """
    Main entry point untuk batch import dari Inventree.
    """
    print("\n" + "═" * 65)
    print("  🏭  Inventree Batch Import Tool")
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

    # ── Ambil daftar produk ───────────────────────────────────────────────────
    if part_ids:
        logger.info(f"📋 Mode: import spesifik {len(part_ids)} part(s)")
        parts = []
        for pid in part_ids:
            ok, part, err = inventree_svc.get_part_by_id(pid)
            if ok and part:
                parts.append(part)
            else:
                logger.warning(f"⚠️  Part {pid} tidak ditemukan: {err}")
    else:
        logger.info("📋 Mengambil semua produk dari Inventree...")
        fetch_limit = limit or 10000
        ok, parts, err = inventree_svc.get_all_parts(limit=fetch_limit)
        if not ok:
            logger.error(f"❌ Gagal mengambil produk: {err}")
            sys.exit(1)
        if limit:
            parts = parts[:limit]

    total = len(parts)
    logger.info(f"✅ {total} produk siap diimport")

    if total == 0:
        print("ℹ️  Tidak ada produk yang perlu diimport.")
        return

    # ── Print ringkasan sebelum mulai ────────────────────────────────────────
    print(f"\n  Produk      : {total}")
    print(f"  Skip exist. : {'Ya' if skip_existing else 'Tidak'}")
    print(f"  Re-embed    : {'Ya' if re_embed else 'Tidak'}")
    print(f"  Workers     : {workers}")
    print(f"  Inventree   : {config.INVENTREE_URL}")
    print()

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats = {
        "imported": 0,
        "re_embedded": 0,
        "skipped": 0,
        "no_image": 0,
        "no_new_image": 0,
        "error": 0,
        "total_downloaded": 0,
        "total_embedded": 0,
    }

    def process_part(part):
        try:
            return import_single_product(
                part,
                inventree_svc,
                faiss_service,
                skip_existing=skip_existing,
                re_embed=re_embed,
            )
        except Exception as e:
            part_id = str(part.get("pk") or part.get("id", "?"))
            logger.error(f"❌ Error pada part {part_id}: {e}")
            return {
                "item_id": part_id,
                "name": part.get("name", "?"),
                "status": "error",
                "images_downloaded": 0,
                "images_embedded": 0,
                "error": str(e),
            }

    # ── Sequential (workers=1) atau Parallel ─────────────────────────────────
    if workers <= 1:
        results = []
        for part in tqdm(parts, desc="Importing", unit="part"):
            res = process_part(part)
            results.append(res)
            _update_stats(stats, res)
            # Save index setiap 50 produk
            if (stats["imported"] + stats["re_embedded"]) % 50 == 0:
                try:
                    faiss_service.save_index()
                except Exception:
                    pass
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(process_part, p): p for p in parts}
            for fut in tqdm(as_completed(futures), total=total, desc="Importing", unit="part"):
                res = fut.result()
                results.append(res)
                _update_stats(stats, res)

    # ── Simpan FAISS index ────────────────────────────────────────────────────
    logger.info("💾 Menyimpan FAISS index ke disk...")
    faiss_service.save_index()

    # ── Ringkasan ─────────────────────────────────────────────────────────────
    _print_summary(stats, total)

    db.disconnect()


def _update_stats(stats: Dict, res: Dict):
    status = res.get("status", "error")
    if status in stats:
        stats[status] += 1
    stats["total_downloaded"] += res.get("images_downloaded", 0)
    stats["total_embedded"] += res.get("images_embedded", 0)


def _print_summary(stats: Dict, total: int):
    print("\n" + "═" * 65)
    print("  📊  RINGKASAN IMPORT")
    print("═" * 65)
    print(f"  Total produk diproses : {total}")
    print(f"  ✅ Berhasil diimport  : {stats['imported']}")
    print(f"  🔄 Re-embedded        : {stats['re_embedded']}")
    print(f"  ⏭️  Di-skip            : {stats['skipped']}")
    print(f"  🖼️  Tidak ada gambar   : {stats['no_image']}")
    print(f"  ➕ Tidak ada gambar baru: {stats['no_new_image']}")
    print(f"  ❌ Error              : {stats['error']}")
    print(f"  ─────────────────────────────────────────────")
    print(f"  📥 Total gambar didownload : {stats['total_downloaded']}")
    print(f"  🧠 Total gambar di-embed   : {stats['total_embedded']}")
    print("═" * 65)
    print()


# ══════════════════════════════════════════════════════════════════════════════
# Re-embed tool: re-embed semua produk yang sudah ada
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
        description="Inventree Batch Import Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python import_inventree.py                      Import semua produk
  python import_inventree.py --limit 100          Import 100 produk pertama
  python import_inventree.py --part-id 42 55 99   Import produk ID 42, 55, 99
  python import_inventree.py --skip-existing      Skip produk yang sudah ada
  python import_inventree.py --re-embed           Tambah gambar baru + re-embed semua
  python import_inventree.py --re-embed-all       Re-embed ulang semua produk di DB
        """,
    )

    parser.add_argument(
        "--limit", type=int, default=None,
        help="Batasi jumlah produk yang diimport"
    )
    parser.add_argument(
        "--part-id", nargs="+", type=int, dest="part_ids", default=None,
        help="Import produk tertentu berdasarkan ID Inventree"
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Skip produk yang sudah ada di database"
    )
    parser.add_argument(
        "--re-embed", action="store_true",
        help="Tambah gambar baru + re-embed semua gambar produk"
    )
    parser.add_argument(
        "--re-embed-all", action="store_true",
        help="Re-embed ulang semua produk yang sudah ada di database"
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
            skip_existing=args.skip_existing,
            re_embed=args.re_embed,
            workers=args.workers,
        )


if __name__ == "__main__":
    main()