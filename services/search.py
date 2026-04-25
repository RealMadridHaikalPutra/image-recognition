"""
FAISS search service for similarity search
Manages FAISS index creation, persistence, and search operations
"""
import numpy as np
import faiss
import config
import os


class FAISSSearchService:
    """Service for FAISS vector search operations"""
    
    def __init__(self, index_path=None, vector_size=None):
        """
        Initialize FAISS search service
        Args:
            index_path: Path to save/load FAISS index
            vector_size: Dimension of embedding vectors
        """
        self.index_path = index_path or config.EMBEDDINGS_INDEX_PATH
        self.vector_size = vector_size or config.EMBEDDING_VECTOR_SIZE
        self.index = None
        self.vector_count = 0
        
        # Try to load existing index
        if os.path.exists(self.index_path):
            self.load_index()
        else:
            self.create_index()
    
    def create_index(self):
        """
        Create new FAISS index
        Uses IndexFlatL2 (flat index with L2 distance)
        """
        try:
            # IndexFlatL2: exact search with L2 distance
            self.index = faiss.IndexFlatL2(self.vector_size)
            self.vector_count = 0
            print(f"✓ Created new FAISS index (dimension: {self.vector_size})")
        except Exception as e:
            print(f"✗ Error creating FAISS index: {e}")
            raise
    
    def add_vector(self, vector, return_index=True):
        """
        Add single vector to index
        Args:
            vector: 1D numpy array of shape (vector_size,)
            return_index: If True, return the index assigned to this vector
        Returns:
            Index of the added vector (if return_index=True)
        """
        try:
            if not isinstance(vector, np.ndarray):
                vector = np.array(vector, dtype=np.float32)
            
            # Ensure vector is float32 and correct shape
            vector = vector.astype(np.float32).reshape(1, -1)
            
            # Store current count before adding
            current_index = self.index.ntotal
            
            # Add vector to index
            self.index.add(vector)
            self.vector_count += 1
            
            if return_index:
                return current_index
        
        except Exception as e:
            print(f"✗ Error adding vector: {e}")
            raise
    
    def add_vectors(self, vectors):
        """
        Add multiple vectors to index
        Args:
            vectors: 2D numpy array of shape (n_vectors, vector_size)
        Returns:
            List of indices assigned to vectors
        """
        try:
            if not isinstance(vectors, np.ndarray):
                vectors = np.array(vectors, dtype=np.float32)
            
            vectors = vectors.astype(np.float32)
            
            # Store current count
            start_index = self.index.ntotal
            
            # Add vectors to index
            self.index.add(vectors)
            self.vector_count += len(vectors)
            
            # Return indices
            return list(range(start_index, start_index + len(vectors)))
        
        except Exception as e:
            print(f"✗ Error adding vectors: {e}")
            raise
    
    def search_vector(self, query_vector, k=5):
        """
        Search for k nearest neighbors
        Args:
            query_vector: 1D numpy array of shape (vector_size,)
            k: Number of nearest neighbors to return
        Returns:
            Tuple (distances, indices)
            - distances: numpy array of L2 distances
            - indices: numpy array of FAISS indices
        """
        try:
            if not isinstance(query_vector, np.ndarray):
                query_vector = np.array(query_vector, dtype=np.float32)
            
            query_vector = query_vector.astype(np.float32).reshape(1, -1)
            
            # Limit k to number of vectors in index
            k = min(k, self.index.ntotal)
            
            if k == 0:
                return np.array([]), np.array([])
            
            # Search
            distances, indices = self.index.search(query_vector, k)
            
            # FAISS returns 2D arrays, flatten them
            distances = distances.flatten()
            indices = indices.flatten()
            
            return distances, indices
        
        except Exception as e:
            print(f"✗ Error searching vector: {e}")
            raise
    
    def search_vectors(self, query_vectors, k=5):
        """
        Search for k nearest neighbors for multiple queries
        Args:
            query_vectors: 2D numpy array of shape (n_queries, vector_size)
            k: Number of nearest neighbors per query
        Returns:
            Tuple (distances, indices)
            - distances: numpy array of shape (n_queries, k)
            - indices: numpy array of shape (n_queries, k)
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
            print(f"✗ Error searching vectors: {e}")
            raise
    
    def save_index(self, path=None):
        """
        Persist FAISS index to disk
        Args:
            path: Path to save index (defaults to self.index_path)
        """
        try:
            if path is None:
                path = self.index_path
            
            os.makedirs(os.path.dirname(path), exist_ok=True)
            faiss.write_index(self.index, str(path))
            print(f"✓ FAISS index saved: {path}")
        
        except Exception as e:
            print(f"✗ Error saving FAISS index: {e}")
            raise
    
    def load_index(self, path=None):
        """
        Load FAISS index from disk
        Args:
            path: Path to load index from (defaults to self.index_path)
        """
        try:
            if path is None:
                path = self.index_path
            
            if not os.path.exists(path):
                raise FileNotFoundError(f"Index file not found: {path}")
            
            self.index = faiss.read_index(str(path))
            self.vector_count = self.index.ntotal
            print(f"✓ FAISS index loaded: {path} ({self.vector_count} vectors)")
        
        except Exception as e:
            print(f"✗ Error loading FAISS index: {e}")
            raise
    
    def get_index_size(self):
        """Get number of vectors in index"""
        return self.index.ntotal if self.index else 0
    
    def reset_index(self):
        """Reset index to empty state"""
        try:
            self.create_index()
            self.vector_count = 0
            print("✓ FAISS index reset")
        except Exception as e:
            print(f"✗ Error resetting index: {e}")
            raise


# Global FAISS service instance
faiss_service = FAISSSearchService()
