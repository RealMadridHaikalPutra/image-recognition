"""
Helper utilities for the application
Provides common functions for validation, formatting, etc.
"""
from functools import wraps
from flask import jsonify
import config


def allowed_file(filename):
    """
    Check if uploaded file has allowed extension
    Args:
        filename: Name of uploaded file
    Returns:
        True if allowed, False otherwise
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


def validate_item_id(item_id):
    """
    Validate item_id format
    Args:
        item_id: Item identifier to validate
    Returns:
        Tuple (is_valid, error_message)
    """
    if not item_id:
        return False, "item_id is required"
    
    if not isinstance(item_id, str):
        return False, "item_id must be a string"
    
    if len(item_id) > 255:
        return False, "item_id too long (max 255 characters)"
    
    if len(item_id.strip()) == 0:
        return False, "item_id cannot be empty"
    
    return True, None


def validate_angle(angle):
    """
    Validate angle value
    Args:
        angle: Angle value to validate
    Returns:
        Tuple (is_valid, error_message)
    """
    if not angle:
        return False, "angle is required"
    
    if not isinstance(angle, str):
        return False, "angle must be a string"
    
    if len(angle) > 50:
        return False, "angle too long (max 50 characters)"
    
    return True, None


def success_response(data=None, message="Success", code=200):
    """
    Create standardized success response
    Args:
        data: Response data
        message: Success message
        code: HTTP status code
    Returns:
        JSON response tuple
    """
    response = {
        'success': True,
        'message': message,
        'data': data
    }
    return jsonify(response), code


def error_response(message="Error", code=400, data=None):
    """
    Create standardized error response
    Args:
        message: Error message
        code: HTTP status code
        data: Additional error data
    Returns:
        JSON response tuple
    """
    response = {
        'success': False,
        'message': message,
        'data': data
    }
    return jsonify(response), code


def format_similarity_score(distance):
    """
    Convert L2 distance to similarity score (0-100)
    Lower L2 distance = higher similarity
    Args:
        distance: L2 distance value
    Returns:
        Similarity score 0-100
    """
    # Simple inverse relationship
    # Assuming distances are typically 0-10
    score = max(0, 100 - (distance * 10))
    return min(100, round(score, 2))


def format_search_result(faiss_index, item_id, distance, image_count=1):
    """
    Format search result for response
    Args:
        faiss_index: FAISS index
        item_id: Product item ID
        distance: L2 distance
        image_count: Number of images for this item
    Returns:
        Formatted result dictionary
    """
    return {
        'item_id': item_id,
        'faiss_index': int(faiss_index),
        'distance': float(distance),
        'similarity_score': format_similarity_score(distance),
        'image_count': image_count
    }


def format_item_details(item_id, images):
    """
    Format item details for response
    Args:
        item_id: Product item ID
        images: List of image records from database
    Returns:
        Formatted item dictionary
    """
    return {
        'item_id': item_id,
        'image_count': len(images),
        'images': [
            {
                'id': img.get('id'),
                'angle': img.get('angle'),
                'file_path': img.get('file_path'),
                'created_at': img.get('created_at').isoformat() if img.get('created_at') else None
            }
            for img in images
        ]
    }


def handle_errors(f):
    """
    Decorator for consistent error handling in routes
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return error_response(f"Invalid input: {str(e)}", 400)
        except FileNotFoundError as e:
            return error_response(f"File not found: {str(e)}", 404)
        except Exception as e:
            return error_response(f"Server error: {str(e)}", 500)
    return decorated_function
