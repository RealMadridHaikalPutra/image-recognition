"""
Embedding service for generating image vectors
Uses simple numpy flatten as placeholder for demonstration
"""
import numpy as np
from PIL import Image
import config


class EmbeddingService:
    """Service for generating image embeddings"""
    
    @staticmethod
    def load_image(image_path):
        """
        Load and preprocess image
        Args:
            image_path: Path to image file
        Returns:
            PIL Image object
        """
        try:
            img = Image.open(image_path)
            # Convert RGBA to RGB if necessary
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            return img
        except Exception as e:
            print(f"✗ Error loading image: {e}")
            raise
    
    @staticmethod
    def resize_image(img, target_size=None):
        """
        Resize image to target size
        Args:
            img: PIL Image object
            target_size: Tuple (width, height), defaults to config.IMAGE_SIZE
        Returns:
            Resized PIL Image
        """
        if target_size is None:
            target_size = config.IMAGE_SIZE
        
        img_resized = img.resize(target_size, Image.Resampling.LANCZOS)
        return img_resized
    
    @staticmethod
    def generate_embedding(image_path):
        """
        Generate embedding vector from image
        Process:
            1. Load image
            2. Resize to 224x224
            3. Convert to numpy array (normalize 0-1)
            4. Flatten to 1D vector
            5. Expand to EMBEDDING_VECTOR_SIZE using random padding
        
        Args:
            image_path: Path to image file
        Returns:
            numpy array of shape (EMBEDDING_VECTOR_SIZE,)
        """
        try:
            # Load and preprocess image
            img = EmbeddingService.load_image(image_path)
            img_resized = EmbeddingService.resize_image(img)
            
            # Convert to numpy array and normalize to [0, 1]
            img_array = np.array(img_resized, dtype=np.float32) / 255.0
            
            # Flatten to 1D
            img_flat = img_array.flatten()  # Shape: (224*224*3,) = (150528,)
            
            # Reduce/expand to EMBEDDING_VECTOR_SIZE
            if len(img_flat) > config.EMBEDDING_VECTOR_SIZE:
                # Take first N dimensions
                embedding = img_flat[:config.EMBEDDING_VECTOR_SIZE]
            else:
                # Pad with random values
                embedding = np.zeros(config.EMBEDDING_VECTOR_SIZE, dtype=np.float32)
                embedding[:len(img_flat)] = img_flat
                # Fill remaining with small random values for diversity
                if len(img_flat) < config.EMBEDDING_VECTOR_SIZE:
                    remaining = config.EMBEDDING_VECTOR_SIZE - len(img_flat)
                    embedding[len(img_flat):] = np.random.randn(remaining) * 0.01
            
            # Normalize embedding (L2 norm)
            embedding = embedding.astype(np.float32)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            return embedding
        
        except Exception as e:
            print(f"✗ Error generating embedding: {e}")
            raise
    
    @staticmethod
    def batch_generate_embeddings(image_paths):
        """
        Generate embeddings for multiple images
        Args:
            image_paths: List of image paths
        Returns:
            numpy array of shape (len(image_paths), EMBEDDING_VECTOR_SIZE)
        """
        embeddings = []
        for path in image_paths:
            try:
                embedding = EmbeddingService.generate_embedding(path)
                embeddings.append(embedding)
            except Exception as e:
                print(f"⚠ Skipping image {path}: {e}")
                continue
        
        if embeddings:
            return np.array(embeddings, dtype=np.float32)
        return np.array([], dtype=np.float32).reshape(0, config.EMBEDDING_VECTOR_SIZE)
