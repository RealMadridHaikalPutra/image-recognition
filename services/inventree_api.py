"""
Inventree API Integration Service
Handles communication with Inventree inventory management system
"""

import requests
from requests.auth import HTTPBasicAuth
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class InventreeAPIService:
    """Service for integrating with Inventree API"""
    
    def __init__(self, base_url: str, username: str, password: str):
        """
        Initialize Inventree API service
        
        Args:
            base_url: Inventree server URL (e.g., https://mirorim.ddns.net:8111/)
            username: API authentication username
            password: API authentication password
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.verify = False  # For self-signed certificates
        
    def get_parts(self, limit: int = 1000) -> Tuple[bool, List[Dict], Optional[str]]:
        """
        Fetch all parts/products from Inventree
        
        Args:
            limit: Maximum number of parts to fetch
            
        Returns:
            Tuple of (success: bool, parts: List[Dict], error: Optional[str])
        """
        try:
            url = f"{self.base_url}/api/part/"
            params = {
                'limit': limit,
                'active': True  # Only get active parts
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle both paginated and direct responses
            if isinstance(data, dict) and 'results' in data:
                parts = data['results']
            elif isinstance(data, list):
                parts = data
            else:
                parts = []
            
            logger.info(f"✓ Fetched {len(parts)} parts from Inventree")
            return True, parts, None
            
        except requests.exceptions.ConnectionError as e:
            msg = f"Cannot connect to Inventree: {str(e)}"
            logger.warning(f"⚠️  {msg}")
            return False, [], msg
        except requests.exceptions.Timeout as e:
            msg = f"Inventree request timeout: {str(e)}"
            logger.warning(f"⚠️  {msg}")
            return False, [], msg
        except Exception as e:
            msg = f"Failed to fetch parts: {str(e)}"
            logger.warning(f"⚠️  {msg}")
            return False, [], msg
    
    def get_part_by_id(self, part_id: int) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Fetch a single part by ID
        
        Args:
            part_id: Inventree part ID
            
        Returns:
            Tuple of (success: bool, part: Optional[Dict], error: Optional[str])
        """
        try:
            url = f"{self.base_url}/api/part/{part_id}/"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            part = response.json()
            logger.info(f"✓ Fetched part: {part.get('name', 'Unknown')}")
            return True, part, None
            
        except Exception as e:
            msg = f"Failed to fetch part {part_id}: {str(e)}"
            logger.warning(f"⚠️  {msg}")
            return False, None, msg
    
    def search_parts(self, query: str, limit: int = 50) -> Tuple[bool, List[Dict], Optional[str]]:
        """
        Search for parts by name or SKU
        
        Args:
            query: Search query (name or SKU)
            limit: Maximum number of results
            
        Returns:
            Tuple of (success: bool, parts: List[Dict], error: Optional[str])
        """
        try:
            url = f"{self.base_url}/api/part/"
            params = {
                'search': query,
                'limit': limit,
                'active': True
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle both paginated and direct responses
            if isinstance(data, dict) and 'results' in data:
                parts = data['results']
            elif isinstance(data, list):
                parts = data
            else:
                parts = []
            
            logger.info(f"✓ Found {len(parts)} parts matching '{query}'")
            return True, parts, None
            
        except Exception as e:
            msg = f"Search failed: {str(e)}"
            logger.warning(f"⚠️  {msg}")
            return False, [], msg
    
    def format_parts_for_dropdown(self, parts: List[Dict]) -> List[Dict]:
        """
        Format parts data for dropdown display
        
        Args:
            parts: List of part dictionaries from API
            
        Returns:
            List of formatted part dictionaries with id, name, sku, description
        """
        formatted = []
        for part in parts:
            try:
                item = {
                    'id': part.get('pk', part.get('id')),
                    'name': part.get('name', 'Unknown'),
                    'sku': part.get('SKU', part.get('keywords', 'N/A')),
                    'description': part.get('description', ''),
                    'category': part.get('category_detail', {}).get('name', 'N/A') if isinstance(part.get('category_detail'), dict) else 'N/A'
                }
                formatted.append(item)
            except Exception as e:
                logger.warning(f"Error formatting part: {e}")
                continue
        
        return formatted
    
    def get_part_images(self, part_id: int) -> Tuple[bool, List[Dict], Optional[str]]:
        """
        Fetch images for a specific part
        
        Args:
            part_id: Inventree part ID
            
        Returns:
            Tuple of (success: bool, images: List[Dict], error: Optional[str])
        """
        try:
            url = f"{self.base_url}/api/part/{part_id}/"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            images = []
            
            # Extract image and thumbnail from part object
            if isinstance(data, dict):
                if 'image' in data and data['image']:
                    images.append({
                        'image': data['image'],
                        'thumbnail': data.get('thumbnail', data['image'])
                    })
            
            logger.info(f"✓ Found {len(images)} images for part {part_id}")
            return True, images, None
            
        except Exception as e:
            msg = f"Failed to fetch images for part {part_id}: {str(e)}"
            logger.warning(f"⚠️  {msg}")
            return False, [], msg
    
    def get_part_image_url(self, part_id: int) -> Optional[str]:
        """
        Get the first/primary image URL for a part
        
        Args:
            part_id: Inventree part ID
            
        Returns:
            Absolute image URL or None if not found
        """
        try:
            success, images, error = self.get_part_images(part_id)
            
            if success and len(images) > 0:
                # Get first image
                first_image = images[0]
                image_url = first_image.get('image', first_image.get('url', None))
                
                # If URL is relative, make it absolute
                if image_url and not image_url.startswith('http'):
                    image_url = f"{self.base_url}{image_url}"
                
                logger.info(f"✓ Retrieved image URL for part {part_id}: {image_url}")
                return image_url
            
            logger.info(f"No images found for part {part_id}")
            return None
            
        except Exception as e:
            logger.warning(f"Error getting part image URL: {e}")
            return None


# Global instance
_inventree_service = None


def get_inventree_service(base_url: str = None, username: str = None, password: str = None) -> Optional[InventreeAPIService]:
    """
    Get or create global Inventree service instance
    
    Args:
        base_url: Inventree API URL
        username: API username
        password: API password
        
    Returns:
        InventreeAPIService instance or None if not configured
    """
    global _inventree_service
    
    if _inventree_service is None:
        if base_url and username and password:
            try:
                _inventree_service = InventreeAPIService(base_url, username, password)
                logger.info("✓ Inventree service initialized")
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize Inventree service: {e}")
                return None
    
    return _inventree_service
