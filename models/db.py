"""
Database connection and query functions using psycopg2
Handles PostgreSQL operations for image metadata and embeddings
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import config


class Database:
    """Database wrapper for PostgreSQL operations"""
    
    def __init__(self, db_url=None):
        """Initialize database connection"""
        self.db_url = db_url or config.DATABASE_URL
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.db_url)
            self.conn.autocommit = False
            print("✓ Connected to PostgreSQL")
        except psycopg2.Error as e:
            print(f"✗ Database connection failed: {e}")
            raise
    
    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def init_tables(self):
        """Create required tables if they don't exist"""
        if not self.conn:
            self.connect()
        
        cur = self.conn.cursor()
        try:
            # Create items_images table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS items_images (
                    id SERIAL PRIMARY KEY,
                    item_id VARCHAR(255) NOT NULL,
                    file_path TEXT NOT NULL,
                    angle VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_item_id ON items_images(item_id);
            """)
            
            # Create embeddings table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id SERIAL PRIMARY KEY,
                    image_id INT REFERENCES items_images(id) ON DELETE CASCADE,
                    item_id VARCHAR(255) NOT NULL,
                    faiss_index INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_embedding_item_id ON embeddings(item_id);
                CREATE INDEX IF NOT EXISTS idx_faiss_index ON embeddings(faiss_index);
            """)
            
            self.conn.commit()
            print("✓ Database tables initialized")
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"✗ Error creating tables: {e}")
            raise
        finally:
            cur.close()
    
    def insert_image(self, item_id, file_path, angle):
        """
        Insert image metadata into items_images table
        Returns: image_id (primary key)
        """
        if not self.conn:
            self.connect()
        
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO items_images (item_id, file_path, angle)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (item_id, file_path, angle))
            
            image_id = cur.fetchone()[0]
            self.conn.commit()
            return image_id
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"✗ Error inserting image: {e}")
            raise
        finally:
            cur.close()
    
    def insert_embedding(self, image_id, item_id, faiss_index):
        """
        Insert embedding metadata into embeddings table
        Returns: embedding_id
        """
        if not self.conn:
            self.connect()
        
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO embeddings (image_id, item_id, faiss_index)
                VALUES (%s, %s, %s)
                RETURNING id;
            """, (image_id, item_id, faiss_index))
            
            embedding_id = cur.fetchone()[0]
            self.conn.commit()
            return embedding_id
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"✗ Error inserting embedding: {e}")
            raise
        finally:
            cur.close()
    
    def get_image_by_id(self, image_id):
        """Get image metadata by ID"""
        if not self.conn:
            self.connect()
        
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SELECT * FROM items_images WHERE id = %s;", (image_id,))
            result = cur.fetchone()
            return dict(result) if result else None
        except psycopg2.Error as e:
            print(f"✗ Error fetching image: {e}")
            return None
        finally:
            cur.close()
    
    def get_embeddings_by_item(self, item_id):
        """Get all embeddings for a specific item"""
        if not self.conn:
            self.connect()
        
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT * FROM embeddings 
                WHERE item_id = %s 
                ORDER BY created_at DESC;
            """, (item_id,))
            results = cur.fetchall()
            return [dict(row) for row in results]
        except psycopg2.Error as e:
            print(f"✗ Error fetching embeddings: {e}")
            return []
        finally:
            cur.close()
    
    def get_all_items(self):
        """Get all unique item_ids"""
        if not self.conn:
            self.connect()
        
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT DISTINCT item_id FROM items_images ORDER BY item_id;")
            results = cur.fetchall()
            return [row[0] for row in results]
        except psycopg2.Error as e:
            print(f"✗ Error fetching items: {e}")
            return []
        finally:
            cur.close()
    
    def get_item_details(self, item_id):
        """Get all images for a specific item"""
        if not self.conn:
            self.connect()
        
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT * FROM items_images 
                WHERE item_id = %s 
                ORDER BY created_at DESC;
            """, (item_id,))
            results = cur.fetchall()
            return [dict(row) for row in results]
        except psycopg2.Error as e:
            print(f"✗ Error fetching item details: {e}")
            return []
        finally:
            cur.close()
    
    def get_faiss_to_item_mapping(self):
        """Get mapping of FAISS index to item_id"""
        if not self.conn:
            self.connect()
        
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT faiss_index, item_id FROM embeddings ORDER BY faiss_index;")
            results = cur.fetchall()
            return {int(row[0]): row[1] for row in results}
        except psycopg2.Error as e:
            print(f"✗ Error fetching FAISS mapping: {e}")
            return {}
        finally:
            cur.close()
    
    def count_embeddings(self):
        """Get total number of embeddings"""
        if not self.conn:
            self.connect()
        
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM embeddings;")
            result = cur.fetchone()
            return result[0] if result else 0
        except psycopg2.Error as e:
            print(f"✗ Error counting embeddings: {e}")
            return 0
        finally:
            cur.close()


# Global database instance
db = Database()
