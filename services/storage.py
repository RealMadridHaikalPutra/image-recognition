"""
File storage service for managing image files
Handles saving and organizing product images by item_id and angle
"""
import os
import shutil
from pathlib import Path
from datetime import datetime
import config


class StorageService:
    """Service for managing image file storage"""
    
    def __init__(self, base_path=None):
        """
        Initialize storage service
        Args:
            base_path: Base directory for uploads (defaults to config.UPLOAD_DIR)
        """
        self.base_path = Path(base_path) if base_path else config.UPLOAD_DIR
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_item_dir(self, item_id):
        """Get directory path for a specific item"""
        item_dir = self.base_path / str(item_id)
        return item_dir
    
    def ensure_item_dir(self, item_id):
        """Create item directory if it doesn't exist"""
        item_dir = self.get_item_dir(item_id)
        item_dir.mkdir(parents=True, exist_ok=True)
        return item_dir
    
    def save_image(self, file_obj, item_id, angle, filename=None):
        """
        Save uploaded image file
        Args:
            file_obj: File object from Flask request
            item_id: Product identifier
            angle: Image angle (front, back, left, right, etc.)
            filename: Optional custom filename (auto-generated if not provided)
        
        Returns:
            Dictionary with:
            - file_path: Relative path to saved file
            - full_path: Absolute path to saved file
            - filename: Actual filename used
        """
        try:
            # Create item directory
            item_dir = self.ensure_item_dir(item_id)
            
            # Generate filename if not provided
            if filename is None:
                # Use angle as filename with extension
                ext = self._get_file_extension(file_obj.filename)
                filename = f"{angle}{ext}"
            
            # Full path to save
            full_path = item_dir / filename
            
            # Save file
            file_obj.save(str(full_path))
            
            # Relative path (for database storage)
            relative_path = f"uploads/{item_id}/{filename}"
            
            print(f"✓ Image saved: {relative_path}")
            
            return {
                'file_path': relative_path,
                'full_path': str(full_path),
                'filename': filename
            }
        
        except Exception as e:
            print(f"✗ Error saving image: {e}")
            raise
    
    def get_image_path(self, item_id, angle):
        """
        Get path to image by item_id and angle
        Args:
            item_id: Product identifier
            angle: Image angle
        Returns:
            Full path if exists, None otherwise
        """
        item_dir = self.get_item_dir(item_id)
        
        # Try common extensions
        for ext in ['.jpg', '.jpeg', '.png', '.gif']:
            path = item_dir / f"{angle}{ext}"
            if path.exists():
                return str(path)
        
        return None
    
    def get_all_images_for_item(self, item_id):
        """
        Get all image paths for an item
        Args:
            item_id: Product identifier
        Returns:
            List of image paths
        """
        item_dir = self.get_item_dir(item_id)
        
        if not item_dir.exists():
            return []
        
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif')
        images = [str(f) for f in item_dir.iterdir() 
                 if f.is_file() and f.suffix.lower() in image_extensions]
        
        return sorted(images)
    
    def delete_image(self, file_path):
        """
        Delete image file
        Args:
            file_path: Relative or absolute path to image
        Returns:
            True if deleted, False otherwise
        """
        try:
            # Handle relative path
            if not os.path.isabs(file_path):
                full_path = self.base_path.parent / file_path
            else:
                full_path = Path(file_path)
            
            if full_path.exists():
                full_path.unlink()
                print(f"✓ Image deleted: {file_path}")
                return True
            else:
                print(f"⚠ Image not found: {file_path}")
                return False
        
        except Exception as e:
            print(f"✗ Error deleting image: {e}")
            return False
    
    def delete_item_directory(self, item_id):
        """
        Delete entire item directory and all images
        Args:
            item_id: Product identifier
        Returns:
            True if deleted, False otherwise
        """
        try:
            item_dir = self.get_item_dir(item_id)
            
            if item_dir.exists():
                shutil.rmtree(item_dir)
                print(f"✓ Item directory deleted: {item_id}")
                return True
            else:
                print(f"⚠ Item directory not found: {item_id}")
                return False
        
        except Exception as e:
            print(f"✗ Error deleting item directory: {e}")
            return False
    
    def move_file(self, src_path, dst_path):
        """
        Move file from source to destination
        Args:
            src_path: Source path
            dst_path: Destination path
        Returns:
            True if moved, False otherwise
        """
        try:
            src = Path(src_path)
            dst = Path(dst_path)
            
            # Create destination directory if needed
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(src), str(dst))
            print(f"✓ File moved: {src_path} → {dst_path}")
            return True
        
        except Exception as e:
            print(f"✗ Error moving file: {e}")
            return False
    
    def get_storage_stats(self):
        """
        Get storage statistics
        Returns:
            Dictionary with stats
        """
        try:
            total_size = 0
            file_count = 0
            item_count = 0
            
            if self.base_path.exists():
                for item_dir in self.base_path.iterdir():
                    if item_dir.is_dir():
                        item_count += 1
                        for file in item_dir.iterdir():
                            if file.is_file():
                                file_count += 1
                                total_size += file.stat().st_size
            
            return {
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count,
                'item_count': item_count
            }
        
        except Exception as e:
            print(f"✗ Error getting storage stats: {e}")
            return {}
    
    @staticmethod
    def _get_file_extension(filename):
        """Extract file extension from filename"""
        if not filename:
            return '.jpg'
        
        _, ext = os.path.splitext(filename)
        if not ext:
            ext = '.jpg'
        
        return ext.lower()
    
    @staticmethod
    def is_allowed_file(filename):
        """Check if file extension is allowed"""
        allowed_ext = config.ALLOWED_EXTENSIONS
        _, ext = os.path.splitext(filename)
        return ext.lower().lstrip('.') in allowed_ext


# Global storage service instance
storage_service = StorageService()
