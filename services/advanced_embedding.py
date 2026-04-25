"""
Advanced Embedding Service using CLIP + Traditional Features + FAISS
Combines vision transformer embeddings with color, texture, and edge features
for superior fashion/product image similarity search.

Reference: Multi-modal feature extraction with weighted fusion
"""

import os
import io
import logging
import warnings
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pickle

import cv2
import numpy as np
import torch
import faiss
from PIL import Image
from tqdm import tqdm
from skimage.feature import local_binary_pattern
from sentence_transformers import SentenceTransformer

import config

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

class AdvancedEmbeddingConfig:
    """Advanced embedding configuration with feature weights"""
    
    # Feature weights (sum = 1.0 for consistency in cosine similarity)
    WEIGHT_CLIP = 0.45           # CLIP/Vision Transformer features
    WEIGHT_COLOR = 0.30          # Color histogram (HSV grid)
    WEIGHT_BRIGHTNESS = 0.08     # Brightness/luminance features
    WEIGHT_TEXTURE = 0.12        # LBP texture descriptors
    WEIGHT_EDGE = 0.05           # Canny edge detection
    WEIGHT_DOMINANT = 0.15       # K-Means dominant colors (NEW)
    
    # Image preprocessing
    IMAGE_SIZE = (224, 224)      # CLIP ViT-B/32 standard size
    GRID_SIZE = 5                # Grid subdivisions for color/brightness
    
    # Batch processing
    BATCH_SIZE = 32              # GPU batch size for CLIP
    
    # Search parameters
    TOP_K = 5                    # Default search results
    IVF_THRESHOLD = 5000         # Use IVFFlat if dataset > 5000 items
    IVF_NLIST = 256              # Number of IVF partitions
    
    # Model
    MODEL_NAME = "clip-ViT-B-32"
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ==================== GLOBAL MODEL INSTANCE ====================

_CLIP_MODEL = None


def get_clip_model() -> SentenceTransformer:
    """
    Load CLIP model once (singleton pattern).
    Caches model in memory for multiple embeddings.
    """
    global _CLIP_MODEL
    if _CLIP_MODEL is None:
        logger.info(f"⚙️  Loading CLIP model on {AdvancedEmbeddingConfig.DEVICE.upper()}...")
        _CLIP_MODEL = SentenceTransformer(
            AdvancedEmbeddingConfig.MODEL_NAME,
            device=AdvancedEmbeddingConfig.DEVICE
        )
        logger.info(f"✅ CLIP model ready on {AdvancedEmbeddingConfig.DEVICE.upper()}")
    return _CLIP_MODEL


# ==================== IMAGE PREPROCESSING ====================

def load_and_preprocess(image_input) -> Optional[np.ndarray]:
    """
    Load image from path, PIL, bytes, or numpy array.
    Resize, align, and crop to standardized format.
    
    Args:
        image_input: Path (str/Path), PIL Image, bytes, or numpy array
        
    Returns:
        Preprocessed RGB image as numpy array (H, W, 3), or None if failed
    """
    try:
        # Load image
        if isinstance(image_input, (str, Path)):
            img = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, Image.Image):
            img = image_input.convert("RGB")
        elif isinstance(image_input, np.ndarray):
            img = Image.fromarray(image_input).convert("RGB")
        else:
            img = Image.open(io.BytesIO(image_input)).convert("RGB")
        
        # Resize for alignment
        img = img.resize(AdvancedEmbeddingConfig.IMAGE_SIZE, Image.LANCZOS)
        img_cv = np.array(img)
        
        # Align and crop
        img_cv = _align_and_crop(img_cv)
        
        # Final resize after crop
        img_cv = np.array(
            Image.fromarray(img_cv).resize(
                AdvancedEmbeddingConfig.IMAGE_SIZE,
                Image.LANCZOS
            )
        )
        
        return img_cv
    
    except Exception as e:
        logger.warning(f"⚠️  Failed to load image: {e}")
        return None


def _align_and_crop(img_cv: np.ndarray) -> np.ndarray:
    """
    Rotate object to be upright, then crop whitespace.
    Handles dark objects on light backgrounds and vice versa.
    
    Args:
        img_cv: BGR/RGB image as numpy array
        
    Returns:
        Aligned and cropped image
    """
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    
    # Otsu threshold (invert for dark objects)
    _, thresh = cv2.threshold(
        gray, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    
    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )
    
    if not contours:
        return img_cv
    
    # Filter large contours (> 0.5% of image area)
    h, w = img_cv.shape[:2]
    min_area = 0.005 * h * w
    large_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    
    if not large_contours:
        return img_cv
    
    cnt = max(large_contours, key=cv2.contourArea)
    
    # Calculate orientation using moments
    m = cv2.moments(cnt)
    if m['mu20'] != m['mu02'] and (m['mu20'] + m['mu02']) > 0:
        theta = 0.5 * np.arctan2(2 * m['mu11'], m['mu20'] - m['mu02'])
        angle_deg = np.rad2deg(theta)
        if m['mu20'] < m['mu02']:
            angle_deg += 90
    else:
        angle_deg = 0
    
    # Only rotate if significant angle (> 5°)
    if abs(angle_deg) > 5:
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle_deg, 1.0)
        img_cv = cv2.warpAffine(
            img_cv, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )
    
    # Crop light background
    gray_rot = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    _, thresh_rot = cv2.threshold(gray_rot, 240, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(thresh_rot)
    
    if coords is not None:
        x, y, ww, hh = cv2.boundingRect(coords)
        pad = 8
        img_cv = img_cv[
            max(0, y - pad): min(h, y + hh + pad),
            max(0, x - pad): min(w, x + ww + pad)
        ]
    
    return img_cv


# ==================== TRADITIONAL FEATURE EXTRACTION ====================

def _l2_norm(vec: np.ndarray) -> np.ndarray:
    """L2 normalize vector for cosine similarity."""
    norm = np.linalg.norm(vec)
    return vec / (norm + 1e-8)


def extract_color_features(img_cv: np.ndarray) -> np.ndarray:
    """
    Extract color histogram from HSV grid.
    Subdivides image into grid cells and extracts median H, S per cell.
    """
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2HSV)
    h, w, _ = hsv.shape
    gs = AdvancedEmbeddingConfig.GRID_SIZE
    
    color_feats = []
    for i in range(gs):
        for j in range(gs):
            patch = hsv[
                i*(h//gs):(i+1)*(h//gs),
                j*(w//gs):(j+1)*(w//gs)
            ]
            if patch.size == 0:
                color_feats.extend([0.0, 0.0])
                continue
            
            color_feats.extend([
                np.median(patch[:, :, 0]),  # Hue
                np.median(patch[:, :, 1])   # Saturation
            ])
    
    return _l2_norm(np.array(color_feats, dtype=np.float32))


def extract_brightness_features(img_cv: np.ndarray) -> np.ndarray:
    """Extract brightness histogram from grid cells."""
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2HSV)
    h, w, _ = hsv.shape
    gs = AdvancedEmbeddingConfig.GRID_SIZE
    
    bright_feats = []
    for i in range(gs):
        for j in range(gs):
            patch = hsv[
                i*(h//gs):(i+1)*(h//gs),
                j*(w//gs):(j+1)*(w//gs)
            ]
            if patch.size == 0:
                bright_feats.append(0.0)
            else:
                bright_feats.append(np.median(patch[:, :, 2]))  # Value/Brightness
    
    return _l2_norm(np.array(bright_feats, dtype=np.float32))


def extract_texture_features(img_cv: np.ndarray) -> np.ndarray:
    """
    Extract LBP (Local Binary Pattern) texture descriptor.
    More descriptive than simple gradients.
    """
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    
    # LBP with radius 3, 24 points, uniform patterns
    lbp = local_binary_pattern(gray, P=24, R=3, method="uniform")
    
    # Histogram of LBP patterns
    t_hist, _ = np.histogram(
        lbp.ravel(),
        bins=np.arange(0, 27),
        range=(0, 26)
    )
    
    return _l2_norm(t_hist.astype(np.float32))


def extract_edge_features(img_cv: np.ndarray) -> np.ndarray:
    """Extract edge density using Canny edge detection."""
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    
    edges = cv2.Canny(gray, 80, 180)
    
    # Histogram of edge intensities
    edge_hist, _ = np.histogram(
        edges,
        bins=4,
        range=(0, 255)
    )
    
    return _l2_norm(edge_hist.astype(np.float32))


def extract_dominant_colors(img_cv: np.ndarray, k: int = 5) -> np.ndarray:
    """
    Extract dominant colors using K-Means clustering.
    More accurate than HSV grid alone.
    """
    pixels = img_cv.reshape(-1, 3).astype(np.float32)
    
    criteria = (
        cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
        10, 1.0
    )
    
    _, labels, centers = cv2.kmeans(
        pixels, k, None, criteria, 3,
        cv2.KMEANS_RANDOM_CENTERS
    )
    
    counts = np.bincount(labels.flatten())
    sorted_idx = np.argsort(-counts)
    
    # Flatten dominant colors into 1D vector
    dominant = centers[sorted_idx].flatten()
    
    return _l2_norm(dominant.astype(np.float32))


def extract_traditional_features(img_cv: np.ndarray) -> Tuple:
    """
    Extract all traditional features in one call.
    Called per CPU (can be parallelized).
    
    Returns:
        Tuple of (color_vec, bright_vec, texture_vec, edge_vec, dominant_vec)
    """
    color_v = extract_color_features(img_cv)
    bright_v = extract_brightness_features(img_cv)
    tex_v = extract_texture_features(img_cv)
    edge_v = extract_edge_features(img_cv)
    dominant_v = extract_dominant_colors(img_cv, k=5)
    
    return color_v, bright_v, tex_v, edge_v, dominant_v


# ==================== CLIP EMBEDDING ====================

def extract_clip_embedding(image_pil: Image.Image) -> np.ndarray:
    """
    Extract CLIP embedding from PIL image.
    
    Args:
        image_pil: PIL Image (RGB)
        
    Returns:
        L2-normalized CLIP embedding (384-dim for ViT-B/32)
    """
    model = get_clip_model()
    
    with torch.no_grad():
        emb = model.encode(
            [image_pil],
            batch_size=1,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
    
    return emb[0].astype(np.float32)


def extract_clip_batch(images_pil: List[Image.Image]) -> np.ndarray:
    """
    Extract CLIP embeddings for batch of images (GPU accelerated).
    
    Args:
        images_pil: List of PIL Images
        
    Returns:
        Array of shape (len(images_pil), 384)
    """
    model = get_clip_model()
    
    with torch.no_grad():
        embs = model.encode(
            images_pil,
            batch_size=AdvancedEmbeddingConfig.BATCH_SIZE,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
    
    return embs.astype(np.float32)


# ==================== COMBINED FEATURE VECTOR ====================

def combine_features(
    clip_emb: np.ndarray,
    color_v: np.ndarray,
    bright_v: np.ndarray,
    tex_v: np.ndarray,
    edge_v: np.ndarray,
    dominant_v: np.ndarray
) -> np.ndarray:
    """
    Combine all features with weighted fusion.
    Final vector is L2-normalized for cosine similarity via inner product.
    
    Args:
        clip_emb: CLIP embedding
        color_v, bright_v, tex_v, edge_v, dominant_v: Traditional features
        
    Returns:
        Combined feature vector (L2-normalized)
    """
    cfg = AdvancedEmbeddingConfig
    
    combined = np.concatenate([
        clip_emb * cfg.WEIGHT_CLIP,
        color_v * cfg.WEIGHT_COLOR,
        bright_v * cfg.WEIGHT_BRIGHTNESS,
        tex_v * cfg.WEIGHT_TEXTURE,
        edge_v * cfg.WEIGHT_EDGE,
        dominant_v * cfg.WEIGHT_DOMINANT,
    ]).astype(np.float32)
    
    # L2 normalize so cosine similarity = inner product on FAISS
    return _l2_norm(combined)


# ==================== MAIN EMBEDDING FUNCTION ====================

class AdvancedEmbeddingService:
    """Service for extracting and managing advanced embeddings"""
    
    @staticmethod
    def generate_embedding(image_input) -> Optional[np.ndarray]:
        """
        Generate combined feature embedding from image.
        
        Args:
            image_input: Path, PIL Image, bytes, or numpy array
            
        Returns:
            Combined feature vector (normalized), or None if failed
        """
        try:
            # Preprocess image
            img_cv = load_and_preprocess(image_input)
            if img_cv is None:
                return None
            
            # Convert to PIL for CLIP
            img_pil = Image.fromarray(img_cv).convert("RGB")
            
            # Extract CLIP embedding
            clip_emb = extract_clip_embedding(img_pil)
            
            # Extract traditional features
            color_v, bright_v, tex_v, edge_v, dominant_v = extract_traditional_features(img_cv)
            
            # Combine with weights
            final_vec = combine_features(
                clip_emb, color_v, bright_v, tex_v, edge_v, dominant_v
            )
            
            return final_vec
        
        except Exception as e:
            logger.error(f"❌ Error generating embedding: {e}")
            return None
    
    @staticmethod
    def generate_batch_embeddings(image_inputs: List) -> np.ndarray:
        """
        Generate embeddings for batch of images (GPU optimized).
        
        Args:
            image_inputs: List of image paths, PIL Images, etc.
            
        Returns:
            Array of shape (len(image_inputs), combined_dim)
        """
        embeddings = []
        
        # Preprocess all images
        imgs_cv = []
        imgs_pil = []
        valid_indices = []
        
        for i, img_input in enumerate(image_inputs):
            img_cv = load_and_preprocess(img_input)
            if img_cv is not None:
                imgs_cv.append(img_cv)
                imgs_pil.append(Image.fromarray(img_cv).convert("RGB"))
                valid_indices.append(i)
        
        if not imgs_pil:
            return np.array([], dtype=np.float32).reshape(0, 1000)  # Dummy dimension
        
        # Extract CLIP embeddings in batch (GPU)
        clip_embs = extract_clip_batch(imgs_pil)
        
        # Extract traditional features (parallelized CPU)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        trad_feats = [None] * len(imgs_cv)
        
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count())) as ex:
            futures = {
                ex.submit(extract_traditional_features, img): i
                for i, img in enumerate(imgs_cv)
            }
            
            for fut in tqdm(as_completed(futures), total=len(imgs_cv),
                          desc="Traditional features", disable=True):
                idx = futures[fut]
                trad_feats[idx] = fut.result()
        
        # Combine features
        for i, (clip_emb, trad_feat) in enumerate(zip(clip_embs, trad_feats)):
            color_v, bright_v, tex_v, edge_v, dominant_v = trad_feat
            final_vec = combine_features(
                clip_emb, color_v, bright_v, tex_v, edge_v, dominant_v
            )
            embeddings.append(final_vec)
        
        return np.array(embeddings, dtype=np.float32)


# ==================== COMPATIBILITY ====================

def generate_embedding(image_path):
    """
    Wrapper function for compatibility with existing code.
    Replaces simple embedding with advanced version.
    """
    return AdvancedEmbeddingService.generate_embedding(image_path)
