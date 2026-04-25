/**
 * Main JavaScript functionality
 */

// Add drag & drop support for file inputs
document.addEventListener('DOMContentLoaded', function() {
    setupFileDragDrop();
    setupFormValidation();
});

/**
 * Setup drag & drop for file inputs
 */
function setupFileDragDrop() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(input => {
        const wrapper = input.closest('.file-input-wrapper');
        if (!wrapper) return;
        
        const dropZone = wrapper.querySelector('.file-input-label');
        if (!dropZone) return;
        
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });
        
        // Highlight drop zone when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.style.borderColor = '#764ba2';
                dropZone.style.background = '#f0f2ff';
            }, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.style.borderColor = '#667eea';
                dropZone.style.background = '#f8f9ff';
            }, false);
        });
        
        // Handle dropped files
        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            input.files = files;
            
            // Trigger change event
            const event = new Event('change', { bubbles: true });
            input.dispatchEvent(event);
        }, false);
        
        // Make label clickable
        dropZone.addEventListener('click', () => {
            input.click();
        });
    });
}

/**
 * Prevent default drag & drop behavior
 */
function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

/**
 * Setup form validation
 */
function setupFormValidation() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Validate file input
            const fileInput = form.querySelector('input[type="file"]');
            if (fileInput && !fileInput.files.length) {
                e.preventDefault();
                alert('Please select an image file');
                return false;
            }
            
            // Validate required fields
            const requiredInputs = form.querySelectorAll('[required]');
            let isValid = true;
            
            requiredInputs.forEach(input => {
                if (!input.value.trim()) {
                    input.style.borderColor = '#f44336';
                    isValid = false;
                } else {
                    input.style.borderColor = '#ddd';
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                alert('Please fill all required fields');
                return false;
            }
        });
    });
}

/**
 * Format bytes to human-readable size
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Validate image file
 */
function validateImageFile(file) {
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif'];
    const maxSize = 10 * 1024 * 1024; // 10MB
    
    if (!allowedTypes.includes(file.type)) {
        return {
            valid: false,
            message: 'Invalid file type. Allowed: JPEG, PNG, GIF'
        };
    }
    
    if (file.size > maxSize) {
        return {
            valid: false,
            message: `File too large. Max: ${formatBytes(maxSize)}`
        };
    }
    
    return { valid: true };
}

/**
 * Show loading state on form submission
 */
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.style.opacity = '0.6';
                submitBtn.style.cursor = 'not-allowed';
                
                // Show loading text
                const originalText = submitBtn.textContent;
                submitBtn.textContent = '⏳ Processing...';
                
                // Restore after timeout (in case something goes wrong)
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.style.opacity = '1';
                    submitBtn.style.cursor = 'pointer';
                    submitBtn.textContent = originalText;
                }, 30000); // 30 seconds timeout
            }
        });
    });
});

/**
 * Smooth scroll to section
 */
function smoothScroll(target) {
    const element = document.querySelector(target);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Close alert after 5 seconds
 */
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.3s ease';
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.style.display = 'none';
            }, 300);
        }, 5000);
    });
});

// Export functions for use in templates
window.formatBytes = formatBytes;
window.validateImageFile = validateImageFile;
window.smoothScroll = smoothScroll;
