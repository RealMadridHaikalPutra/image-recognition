"""
Advanced FAISS Search Service
Manages vector indexing and similarity search with automatic index optimization.
"""

import numpy as np
import faiss
import config
import os
import logging

logger = logging.getLogger(__name__)


class AdvancedFAISSService:
    """
    FAISS service for managing vector indices.
    Automatically chooses between IVFFlat (large) and FlatIP (small) indices.
    """
    
    def __init__(self, index_path=None, vector_size=None, ivf_threshold=5000):
        """
        Initialize FAISS search service.
        
        Args:
            index_path: Path to save/load FAISS index
            vector_size: Dimension of embedding vectors
            ivf_threshold: Use IVFFlat if dataset > this size
        """
        self.index_path = index_path or config.EMBEDDINGS_INDEX_PATH
        self.vector_size = vector_size or 1000  # Combined features dimension
        self.ivf_threshold = ivf_threshold
        self.index = None
        self.vector_count = 0
        self.use_ivf = False
        
        # Try to load existing index
        if os.path.exists(self.index_path):
            self.load_index()
        else:
            self.create_index()
    
    def create_index(self, use_ivf=None):
        """
        Create new FAISS index.
        Uses IndexFlatIP for exact search (cosine via inner product on normalized vectors).
        Or IndexIVFFlat for approximate search on large datasets.
        
        Args:
            use_ivf: Force IVF (None = auto-detect based on data size)
        """
        try:
            if use_ivf is None:
                use_ivf = self.vector_count > self.ivf_threshold
            
            self.use_ivf = use_ivf
            
            if use_ivf:
                # IVFFlat for large datasets (faster but approximate)
                nlist = min(256, max(32, self.vector_count // 10))
                quantizer = faiss.IndexFlatIP(self.vector_size)
                self.index = faiss.IndexIVFFlat(
                    quantizer,
                    self.vector_size,
                    nlist,
                    faiss.METRIC_INNER_PRODUCT
                )
                logger.info(f"✓ Created IVFFlat index (nlist={nlist})")
            else:
                # FlatIP for small datasets (exact, very fast)
                self.index = faiss.IndexFlatIP(self.vector_size)
                logger.info(f"✓ Created FlatIP index")
            
            self.vector_count = 0
        
        except Exception as e:
            logger.error(f"❌ Error creating FAISS index: {e}")
            raise
    
    def add_vector(self, vector, return_index=True):
        """
        Add single vector to index.
        
        Args:
            vector: 1D numpy array (should be L2-normalized)
            return_index: If True, return assigned index
            
        Returns:
            Index of added vector
        """
        try:
            if not isinstance(vector, np.ndarray):
                vector = np.array(vector, dtype=np.float32)
            
            vector = vector.astype(np.float32).reshape(1, -1)
            actual_dim = vector.shape[1]
            
            # If dimension mismatch, recreate index with correct dimension
            if self.index is not None and actual_dim != self.index.d:
                logger.warning(f"⚠️  Dimension mismatch: expected {self.index.d}, got {actual_dim}")
                logger.warning(f"   Recreating FAISS index with correct dimension {actual_dim}")
                self.vector_size = actual_dim
                self.index = None
                self.vector_count = 0
                self.create_index()
            
            # Create index if not exists
            if self.index is None:
                self.vector_size = actual_dim
                self.create_index()
            
            # For IVF, must train first if this is first batch
            if self.use_ivf and self.index.ntotal == 0:
                self.index.train(vector)
            
            current_index = self.index.ntotal
            self.index.add(vector)
            self.vector_count += 1
            
            if return_index:
                return current_index
        
        except Exception as e:
            logger.error(f"❌ Error adding vector: {e}")
            raise
    
    def add_vectors(self, vectors):
        """
        Add multiple vectors to index.
        
        Args:
            vectors: 2D numpy array (n_vectors, dim)
            
        Returns:
            List of indices assigned
        """
        try:
            if not isinstance(vectors, np.ndarray):
                vectors = np.array(vectors, dtype=np.float32)
            
            vectors = vectors.astype(np.float32)
            actual_dim = vectors.shape[1]
            
            # If dimension mismatch, recreate index with correct dimension
            if self.index is not None and actual_dim != self.index.d:
                logger.warning(f"⚠️  Dimension mismatch: expected {self.index.d}, got {actual_dim}")
                logger.warning(f"   Recreating FAISS index with correct dimension {actual_dim}")
                self.vector_size = actual_dim
                self.index = None
                self.vector_count = 0
                self.create_index()
            
            # Create index if not exists
            if self.index is None:
                self.vector_size = actual_dim
                self.create_index()
            
            # For IVF, train if empty
            if self.use_ivf and self.index.ntotal == 0:
                # Train on subset if very large
                train_size = min(40000, len(vectors))
                if len(vectors) > train_size:
                    self.index.train(vectors[:train_size])
                else:
                    self.index.train(vectors)
            
            start_index = self.index.ntotal
            self.index.add(vectors)
            self.vector_count += len(vectors)
            
            return list(range(start_index, start_index + len(vectors)))
        
        except Exception as e:
            logger.error(f"❌ Error adding vectors: {e}")
            raise
    
    def search_vector(self, query_vector, k=5):
        """
        Search for k nearest neighbors.
        
        Args:
            query_vector: 1D query vector (L2-normalized)
            k: Number of results
            
        Returns:
            Tuple (distances, indices)
        """
        try:
            if not isinstance(query_vector, np.ndarray):
                query_vector = np.array(query_vector, dtype=np.float32)
            
            query_vector = query_vector.astype(np.float32).reshape(1, -1)
            
            k = min(k, self.index.ntotal)
            
            if k == 0:
                return np.array([]), np.array([])
            
            distances, indices = self.index.search(query_vector, k)
            
            return distances.flatten(), indices.flatten()
        
        except Exception as e:
            logger.error(f"❌ Error searching: {e}")
            raise
    
    def search_vectors(self, query_vectors, k=5):
        """
        Search for k nearest neighbors for multiple queries.
        
        Args:
            query_vectors: 2D array (n_queries, dim)
            k: Number of results per query
            
        Returns:
            Tuple (distances, indices)
        """
        try:
            if not isinstance(query_vectors, np.ndarray):
                query_vectors = np.array(query_vectors, dtype=np.float32)
            
            query_vectors = query_vectors.astype(np.float32)
            
            k = min(k, self.index.ntotal)
            
            if k == 0:
                return np.array([]), np.array([])
            
            distances, indices = self.index.search(query_vectors, k)
            
            return distances, indices
        
        except Exception as e:
            logger.error(f"❌ Error searching vectors: {e}")
            raise
    
    def save_index(self, path=None):
        """
        Persist FAISS index to disk.
        
        Args:
            path: Output path (defaults to self.index_path)
        """
        try:
            if path is None:
                path = self.index_path
            
            os.makedirs(os.path.dirname(path), exist_ok=True)
            faiss.write_index(self.index, str(path))
            logger.info(f"✓ FAISS index saved: {path}")
        
        except Exception as e:
            logger.error(f"❌ Error saving index: {e}")
            raise
    
    def load_index(self, path=None):
        """
        Load FAISS index from disk.
        
        Args:
            path: Input path (defaults to self.index_path)
        """
        try:
            if path is None:
                path = self.index_path
            
            if not os.path.exists(path):
                raise FileNotFoundError(f"Index not found: {path}")
            
            self.index = faiss.read_index(str(path))
            self.vector_count = self.index.ntotal
            
            # Detect index type
            self.use_ivf = isinstance(self.index, faiss.IndexIVFFlat)
            
            logger.info(f"✓ FAISS index loaded: {path} ({self.vector_count} vectors)")
        
        except Exception as e:
            logger.error(f"❌ Error loading index: {e}")
            raise
    
    def get_index_size(self):
        """Get total number of vectors in index"""
        return self.index.ntotal if self.index else 0
    
    def reset_index(self):
        """Reset index to empty state"""
        try:
            self.create_index(use_ivf=False)
            self.vector_count = 0
            logger.info("✓ FAISS index reset")
        except Exception as e:
            logger.error(f"❌ Error resetting index: {e}")
            raise
    
    def get_index_info(self):
        """Get detailed index information"""
        return {
            'ntotal': self.index.ntotal if self.index else 0,
            'dimension': self.vector_size,
            'type': 'IVFFlat' if self.use_ivf else 'FlatIP',
            'path': str(self.index_path)
        }


# Global FAISS service instance (lazy init)
faiss_service = None


def get_faiss_service(vector_size=1000, ivf_threshold=5000):
    """Get or create global FAISS service instance"""
    global faiss_service
    if faiss_service is None:
        faiss_service = AdvancedFAISSService(
            vector_size=vector_size,
            ivf_threshold=ivf_threshold
        )
    return faiss_service
