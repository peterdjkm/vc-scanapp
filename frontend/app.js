// Configuration
// In production, use relative URLs (same domain)
// In development, use localhost
const API_BASE_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:5001' 
    : ''; // Empty string = same origin

// DOM Elements
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const detectionCanvas = document.getElementById('detection-canvas');
const captureBtn = document.getElementById('capture-btn');
const scanFrameElement = document.querySelector('.scan-frame');
const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('file-input');
const cameraSection = document.getElementById('camera-section');
const processingSection = document.getElementById('processing-section');
const resultsSection = document.getElementById('results-section');
const contactsSection = document.getElementById('contacts-section');
const contactsList = document.getElementById('contacts-list');
const successMessage = document.getElementById('success-message');
const errorMessage = document.getElementById('error-message');
const errorText = document.getElementById('error-text');
const duplicateModal = document.getElementById('duplicate-modal');
const duplicateInfo = document.getElementById('duplicate-info');
const contactsSearch = document.getElementById('contacts-search');

// Field inputs
const nameInput = document.getElementById('name');
const orgInput = document.getElementById('organisation');
const mobileInput = document.getElementById('mobile');
const landlineInput = document.getElementById('landline');
const emailInput = document.getElementById('email');
const designationInput = document.getElementById('designation');

// Confidence displays
const confidenceBadge = document.getElementById('confidence-badge');
const confidenceValue = document.getElementById('confidence-value');
const rawTextDisplay = document.getElementById('raw-text');
const extractedTextDisplay = document.getElementById('extracted-text');
const extractionMethodDisplay = document.getElementById('extraction-method');

// State
let stream = null;
let currentImageData = null;
let detectionContext = null;
let detectionActive = false;
let lastDetectedBounds = null;
let scanFrame = null;
let boundsHistory = []; // Store recent bounds for smoothing
const MAX_HISTORY = 5; // Number of frames to average
let currentDuplicateInfo = null; // Store duplicate info for overwrite
let pendingContactData = null; // Store contact data pending save

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    // Don't auto-initialize camera - wait for user to click "Scan New Card"
});

// Show camera section
function showCamera() {
    const homepageActions = document.getElementById('homepage-actions');
    const cameraSection = document.getElementById('camera-section');
    const resultsSection = document.getElementById('results-section');
    const contactsSection = document.getElementById('contacts-section');
    
    homepageActions.classList.add('hidden');
    contactsSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    cameraSection.classList.remove('hidden');
    
    // Initialize camera when showing camera section
    if (!stream) {
        initializeCamera();
    }
}

// Initialize camera
async function initializeCamera() {
    try {
        // Check if getUserMedia is available
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            // iOS Safari requires HTTPS (except localhost)
            const isLocalhost = window.location.hostname === 'localhost' || 
                               window.location.hostname === '127.0.0.1';
            const isHTTPS = window.location.protocol === 'https:';
            
            if (!isHTTPS && !isLocalhost) {
                throw new Error('HTTPS_REQUIRED');
            } else {
                throw new Error('Camera API not available. Please use a modern browser.');
            }
        }
        
        // Request camera access - prefer back camera (environment)
        try {
            // Try back camera first
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    facingMode: 'environment' // Back camera
                } 
            });
        } catch (error) {
            // Fallback to any available camera if back camera fails
            console.warn('Back camera not available, trying any camera:', error);
            stream = await navigator.mediaDevices.getUserMedia({ video: true });
        }
        
        video.srcObject = stream;
        captureBtn.disabled = false;
        hideError();
    } catch (error) {
        // Log full error details for debugging
        console.error('=== CAMERA ERROR ===');
        console.error('Error object:', error);
        console.error('Error name:', error.name);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
        console.error('Full error:', JSON.stringify(error, Object.getOwnPropertyNames(error)));
        console.error('Protocol:', window.location.protocol);
        console.error('Hostname:', window.location.hostname);
        console.error('User Agent:', navigator.userAgent);
        console.error('MediaDevices available:', !!navigator.mediaDevices);
        console.error('getUserMedia available:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));
        console.error('===================');
        
        let errorMsg = 'Camera access denied. ';
        
        // Check for HTTPS requirement (iOS Safari)
        if (error.message === 'HTTPS_REQUIRED' || 
            (!navigator.mediaDevices && window.location.protocol !== 'https:' && 
             window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1')) {
            errorMsg = '⚠️ iOS Safari requires HTTPS for camera access. ';
            errorMsg += 'Options: 1) Use file upload, 2) Access via localhost, or 3) Deploy to Render.io (automatic HTTPS)';
        } else if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
            errorMsg = 'Camera permission denied. Please allow camera access in your browser settings.';
        } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
            errorMsg = 'No camera found. Please use file upload.';
        } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
            errorMsg = 'Camera is in use. Please close other apps and try again.';
        } else if (error.name === 'TypeError' || error.message.includes('not available')) {
            errorMsg = 'Camera API not available. ';
            if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
                errorMsg += 'iOS Safari requires HTTPS (except localhost). Use file upload or deploy to Render.io.';
            } else {
                errorMsg += 'Please use a modern browser or file upload.';
            }
        } else {
            errorMsg += `Error: ${error.name} - ${error.message || 'Unknown error'}`;
        }
        
        showError(errorMsg);
        captureBtn.disabled = true;
    }
}

// Initialize border detection
function initializeBorderDetection() {
    if (!detectionCanvas || !video) return;
    
    try {
        // Set detection canvas size to match video
        detectionCanvas.width = video.videoWidth;
        detectionCanvas.height = video.videoHeight;
        detectionContext = detectionCanvas.getContext('2d');
        
        // Get scan frame element
        scanFrame = scanFrameElement;
        
        // Start continuous border detection
        startBorderDetection();
    } catch (error) {
        console.error('Border detection init error (non-blocking):', error);
        // Continue without detection - camera still works
    }
}

// Start real-time border detection
function startBorderDetection() {
    if (!detectionContext || !video) return;
    
    detectionActive = true;
    let lastTime = 0;
    
    const detectLoop = (currentTime) => {
        if (!detectionActive || !video || video.readyState !== video.HAVE_ENOUGH_DATA) {
            if (detectionActive) {
                requestAnimationFrame(detectLoop);
            }
            return;
        }
        
        // Detect every 200ms (5 times per second - good balance)
        if (currentTime - lastTime >= 200) {
            try {
                detectCardBorders();
            } catch (error) {
                console.error('Border detection error (non-blocking):', error);
            }
            lastTime = currentTime;
        }
        
        requestAnimationFrame(detectLoop);
    };
    
    requestAnimationFrame(detectLoop);
}

// Stop border detection
function stopBorderDetection() {
    detectionActive = false;
    lastDetectedBounds = null;
    if (scanFrame) {
        scanFrame.style.display = 'none';
    }
}

// Detect card borders using edge detection
function detectCardBorders() {
    if (!video || !detectionContext || video.readyState !== video.HAVE_ENOUGH_DATA) {
        return;
    }
    
    const width = detectionCanvas.width;
    const height = detectionCanvas.height;
    
    if (width === 0 || height === 0) return;
    
    // Draw current video frame to detection canvas
    detectionContext.drawImage(video, 0, 0, width, height);
    
    // Get image data for processing
    const imageData = detectionContext.getImageData(0, 0, width, height);
    const data = imageData.data;
    
    // Find card bounds with improved algorithm
    const bounds = findCardBounds(data, width, height);
    
    if (bounds) {
        // Add to history for smoothing
        boundsHistory.push(bounds);
        if (boundsHistory.length > MAX_HISTORY) {
            boundsHistory.shift(); // Remove oldest
        }
        
        // Calculate smoothed bounds (average of recent detections)
        const smoothedBounds = smoothBounds(boundsHistory);
        
        // Only update if the change is significant (prevents jitter)
        if (!lastDetectedBounds || isSignificantChange(smoothedBounds, lastDetectedBounds)) {
            lastDetectedBounds = smoothedBounds;
            // Update visual feedback
            updateScanFrame(smoothedBounds, width, height);
        }
    } else {
        // Only hide if we've had multiple consecutive failures
        if (boundsHistory.length > 0) {
            boundsHistory = []; // Clear history
        }
        
        // Only hide after a few failed detections
        if (boundsHistory.length === 0 && lastDetectedBounds) {
            // Keep showing last known bounds for a moment (hysteresis)
            setTimeout(() => {
                if (boundsHistory.length === 0) {
                    if (scanFrame) {
                        scanFrame.style.display = 'none';
                    }
                    const instruction = document.querySelector('.instruction');
                    if (instruction) {
                        instruction.textContent = 'Position card within frame';
                        instruction.style.color = 'white';
                    }
                    lastDetectedBounds = null;
                }
            }, 500); // Wait 500ms before hiding
        }
    }
}

// Smooth bounds by averaging recent detections
function smoothBounds(history) {
    if (history.length === 0) return null;
    if (history.length === 1) return history[0];
    
    // Calculate average of all bounds in history
    let sumX = 0, sumY = 0, sumW = 0, sumH = 0;
    for (const bounds of history) {
        sumX += bounds.x;
        sumY += bounds.y;
        sumW += bounds.width;
        sumH += bounds.height;
    }
    
    return {
        x: Math.round(sumX / history.length),
        y: Math.round(sumY / history.length),
        width: Math.round(sumW / history.length),
        height: Math.round(sumH / history.length)
    };
}

// Check if change is significant enough to update display
function isSignificantChange(newBounds, oldBounds) {
    const threshold = 0.1; // 10% change threshold
    const dx = Math.abs(newBounds.x - oldBounds.x) / oldBounds.width;
    const dy = Math.abs(newBounds.y - oldBounds.y) / oldBounds.height;
    const dw = Math.abs(newBounds.width - oldBounds.width) / oldBounds.width;
    const dh = Math.abs(newBounds.height - oldBounds.height) / oldBounds.height;
    
    // Update if any dimension changed by more than threshold
    return dx > threshold || dy > threshold || dw > threshold || dh > threshold;
}

// Update scan frame to show detected card border
function updateScanFrame(bounds, videoWidth, videoHeight) {
    if (!scanFrame || !video) return;
    
    const container = scanFrame.closest('.camera-container');
    if (!container) return;
    
    const containerRect = container.getBoundingClientRect();
    
    // Calculate position relative to container
    const scaleX = containerRect.width / videoWidth;
    const scaleY = containerRect.height / videoHeight;
    
    // Calculate pixel positions
    const leftPx = bounds.x * scaleX;
    const topPx = bounds.y * scaleY;
    const widthPx = bounds.width * scaleX;
    const heightPx = bounds.height * scaleY;
    
    // Update scan frame position and size
    scanFrame.style.left = `${leftPx}px`;
    scanFrame.style.top = `${topPx}px`;
    scanFrame.style.width = `${widthPx}px`;
    scanFrame.style.height = `${heightPx}px`;
    scanFrame.style.display = 'block';
    scanFrame.style.borderColor = '#10B981'; // Green when detected
    scanFrame.style.boxShadow = '0 0 0 9999px rgba(0, 0, 0, 0.5), 0 0 20px rgba(16, 185, 129, 0.5)';
    
    // Update instruction text
    const instruction = document.querySelector('.instruction');
    if (instruction) {
        instruction.textContent = '✓ Card detected - Ready to capture!';
        instruction.style.color = '#10B981';
    }
}

// Find card boundaries using improved edge detection
function findCardBounds(imageData, width, height) {
    // Downsample for performance (process every 3rd pixel for better accuracy)
    const scale = 3;
    const w = Math.floor(width / scale);
    const h = Math.floor(height / scale);
    
    // Convert to grayscale and detect edges with better algorithm
    const edges = new Uint8Array(w * h);
    const gradients = new Float32Array(w * h);
    let maxGradient = 0;
    
    // Improved edge detection using Sobel-like operator
    for (let y = 1; y < h - 1; y++) {
        for (let x = 1; x < w - 1; x++) {
            const px = x * scale;
            const py = y * scale;
            
            // Sample 3x3 neighborhood for better edge detection
            let gx = 0, gy = 0;
            for (let dy = -1; dy <= 1; dy++) {
                for (let dx = -1; dx <= 1; dx++) {
                    const idx = ((py + dy * scale) * width + (px + dx * scale)) * 4;
                    const gray = (imageData[idx] + imageData[idx + 1] + imageData[idx + 2]) / 3;
                    
                    // Sobel operator weights
                    if (dx !== 0) gx += gray * dx * (dx === 0 ? 0 : (dx > 0 ? 1 : -1));
                    if (dy !== 0) gy += gray * dy * (dy === 0 ? 0 : (dy > 0 ? 1 : -1));
                }
            }
            
            const magnitude = Math.sqrt(gx * gx + gy * gy);
            gradients[y * w + x] = magnitude;
            maxGradient = Math.max(maxGradient, magnitude);
        }
    }
    
    // Adaptive threshold (more conservative to reduce false positives)
    const threshold = maxGradient * 0.25; // Lower threshold for better detection
    for (let i = 0; i < edges.length; i++) {
        edges[i] = gradients[i] > threshold ? 255 : 0;
    }
    
    // Find edges along borders with improved scanning
    const margin = 0.08; // Smaller margin for better edge detection
    const minX = Math.floor(width * margin);
    const maxX = Math.floor(width * (1 - margin));
    const minY = Math.floor(height * margin);
    const maxY = Math.floor(height * (1 - margin));
    
    let topEdge = null, bottomEdge = null, leftEdge = null, rightEdge = null;
    let maxTop = 0, maxBottom = 0, maxLeft = 0, maxRight = 0;
    
    // Scan for horizontal edges (top and bottom) - improved algorithm
    const horizontalScanWidth = Math.floor((maxX - minX) / scale);
    const minEdgeDensity = horizontalScanWidth * 0.15; // At least 15% of width must have edges
    
    for (let y = Math.floor(minY / scale); y < Math.floor(maxY / scale); y++) {
        let edgeCount = 0;
        for (let x = Math.floor(minX / scale); x < Math.floor(maxX / scale); x++) {
            if (edges[y * w + x] > 0) edgeCount++;
        }
        
        // Require minimum edge density to avoid false positives
        if (edgeCount >= minEdgeDensity) {
            if (edgeCount > maxTop && y < h * 0.45) {
                maxTop = edgeCount;
                topEdge = y * scale;
            }
            if (edgeCount > maxBottom && y > h * 0.55) {
                maxBottom = edgeCount;
                bottomEdge = y * scale;
            }
        }
    }
    
    // Scan for vertical edges (left and right) - improved algorithm
    const verticalScanHeight = Math.floor((maxY - minY) / scale);
    const minVerticalEdgeDensity = verticalScanHeight * 0.15; // At least 15% of height must have edges
    
    for (let x = Math.floor(minX / scale); x < Math.floor(maxX / scale); x++) {
        let edgeCount = 0;
        for (let y = Math.floor(minY / scale); y < Math.floor(maxY / scale); y++) {
            if (edges[y * w + x] > 0) edgeCount++;
        }
        
        // Require minimum edge density
        if (edgeCount >= minVerticalEdgeDensity) {
            if (edgeCount > maxLeft && x < w * 0.45) {
                maxLeft = edgeCount;
                leftEdge = x * scale;
            }
            if (edgeCount > maxRight && x > w * 0.55) {
                maxRight = edgeCount;
                rightEdge = x * scale;
            }
        }
    }
    
    // Validate bounds with stricter criteria
    if (topEdge && bottomEdge && leftEdge && rightEdge && 
        bottomEdge > topEdge && rightEdge > leftEdge) {
        const cardHeight = bottomEdge - topEdge;
        const cardWidth = rightEdge - leftEdge;
        
        // Stricter validation - ensure reasonable size and aspect ratio
        const aspectRatio = cardWidth / cardHeight;
        const minWidth = width * 0.3;  // At least 30% of frame width
        const minHeight = height * 0.3; // At least 30% of frame height
        const maxWidth = width * 0.95;  // At most 95% of frame width
        const maxHeight = height * 0.95; // At most 95% of frame height
        
        // Validate aspect ratio (business cards are typically 1.5:1 to 2:1, but allow wider range)
        if (aspectRatio >= 0.5 && aspectRatio <= 2.5 &&
            cardWidth >= minWidth && cardHeight >= minHeight &&
            cardWidth <= maxWidth && cardHeight <= maxHeight) {
            
            // Additional check: ensure bounds are not too small relative to frame
            const areaRatio = (cardWidth * cardHeight) / (width * height);
            if (areaRatio >= 0.15 && areaRatio <= 0.9) { // Between 15% and 90% of frame
                return {
                    x: leftEdge,
                    y: topEdge,
                    width: cardWidth,
                    height: cardHeight
                };
            }
        }
    }
    
    return null;
}

// Lock video orientation to prevent auto-rotation
function lockVideoOrientation() {
    if (!video || !stream) return;
    
    // Get video track settings
    const videoTrack = stream.getVideoTracks()[0];
    if (!videoTrack) return;
    
    const settings = videoTrack.getSettings();
    const videoWidth = video.videoWidth || settings.width;
    const videoHeight = video.videoHeight || settings.height;
    
    // Determine if video is naturally portrait or landscape
    const isPortrait = videoHeight > videoWidth;
    
    // Force video to display in portrait orientation
    // This prevents browser from auto-rotating based on device orientation
    video.style.transform = 'none';
    video.style.webkitTransform = 'none';
    video.style.mozTransform = 'none';
    video.style.msTransform = 'none';
    
    // If video is naturally landscape, we need to rotate it to portrait
    // But we want to keep it as-is (WYSIWYG), so we just lock the transform
    // The CSS will handle keeping it in portrait orientation
    
    // Ensure container maintains aspect ratio
    const container = document.querySelector('.camera-container');
    if (container) {
        container.style.transform = 'none';
        container.style.webkitTransform = 'none';
    }
}

// Setup event listeners
function setupEventListeners() {
    captureBtn.addEventListener('click', captureImage);
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileUpload);
    
    document.getElementById('save-btn').addEventListener('click', saveContact);
    document.getElementById('retry-btn').addEventListener('click', resetScanner);
    document.getElementById('scan-card-btn').addEventListener('click', showCamera);
    document.getElementById('view-contacts-btn').addEventListener('click', showContactsList);
    document.getElementById('close-contacts-btn').addEventListener('click', hideContactsList);
    contactsSearch.addEventListener('input', filterContacts);
    
    // Duplicate modal buttons
    document.getElementById('overwrite-btn').addEventListener('click', overwriteContact);
    document.getElementById('save-new-btn').addEventListener('click', saveAsNewContact);
    document.getElementById('cancel-save-btn').addEventListener('click', cancelSave);
    
    // Prevent orientation changes from affecting video
    window.addEventListener('orientationchange', () => {
        setTimeout(lockVideoOrientation, 100);
    });
    
    // Also handle resize (some devices trigger resize instead of orientationchange)
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(lockVideoOrientation, 100);
    });
}

// Capture image from camera
function captureImage() {
    try {
        // Check if video is ready
        if (!video || video.readyState !== video.HAVE_ENOUGH_DATA) {
            console.error('Video not ready:', video?.readyState);
            showError('Camera not ready. Please wait a moment and try again.');
            return;
        }
        
        // Stop border detection during capture
        stopBorderDetection();
        
        const context = canvas.getContext('2d');
        
        // Use video's natural dimensions
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        console.log('Capturing image:', canvas.width, 'x', canvas.height);
        
        // Draw video to canvas
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Convert to blob
        canvas.toBlob((blob) => {
            if (!blob) {
                console.error('Failed to create blob from canvas');
                showError('Failed to capture image. Please try again.');
                return;
            }
            console.log('Image captured, size:', blob.size, 'bytes');
            processImage(blob);
        }, 'image/jpeg', 0.9);
    } catch (error) {
        console.error('Capture error:', error);
        showError('Failed to capture image: ' + error.message);
    }
}

// Handle file upload
function handleFileUpload(event) {
    const file = event.target.files[0];
    if (file) {
        processImage(file);
    }
}

// Process image
async function processImage(imageFile) {
    try {
        // Stop camera stream
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
        
        // Show processing
        showProcessing();
        hideError();
        hideSuccess();
        
        // Convert to base64
        const base64 = await fileToBase64(imageFile);
        currentImageData = base64;
        
        // Send to API
        console.log('Sending image to API...', `${API_BASE_URL}/api/process-card`);
        const response = await fetch(`${API_BASE_URL}/api/process-card`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image: base64,
                user_id: 'default'
            })
        });
        
        console.log('API Response status:', response.status, response.statusText);
        
        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch (e) {
                errorData = { error: `HTTP ${response.status}: ${response.statusText}` };
            }
            console.error('API Error:', errorData);
            throw new Error(errorData.error || `Failed to process image (${response.status})`);
        }
        
        const data = await response.json();
        console.log('API Response data:', data);
        
        if (data.success) {
            displayResults(data);
        } else {
            console.error('API returned success=false:', data);
            throw new Error(data.error || 'Processing failed');
        }
        
    } catch (error) {
        console.error('Processing error:', error);
        console.error('Error stack:', error.stack);
        showError(error.message || 'Failed to process image. Please try again.');
        resetToCamera();
    }
}

// Display results
function displayResults(data) {
    const extracted = data.extracted_data || {};
    const overallConfidence = (data.overall_confidence * 100).toFixed(1);
    
    // Update confidence badge
    confidenceValue.textContent = overallConfidence;
    confidenceBadge.className = 'confidence-badge';
    if (data.overall_confidence >= 0.95) {
        confidenceBadge.style.background = '#10B981';
    } else if (data.overall_confidence >= 0.85) {
        confidenceBadge.style.background = '#F59E0B';
    } else {
        confidenceBadge.style.background = '#EF4444';
    }
    
    // Populate fields
    populateField('name', extracted.name);
    populateField('organisation', extracted.organisation);
    populateField('mobile', extracted.mobile_number);
    populateField('landline', extracted.landline_number);
    populateField('email', extracted.email_id);
    populateField('designation', extracted.designation);
    
    // Show raw OCR text
    if (data.raw_text) {
        rawTextDisplay.textContent = data.raw_text;
    }
    
    // Show extracted text (formatted JSON)
    const extractedData = {};
    Object.keys(data.extracted_data || {}).forEach(field => {
        const fieldData = data.extracted_data[field];
        extractedData[field] = {
            value: fieldData.value || null,
            confidence: fieldData.confidence,
            source: fieldData.source
        };
    });
    extractedTextDisplay.textContent = JSON.stringify(extractedData, null, 2);
    
    // Show extraction method
    const method = data.parsing_metadata?.extraction_method || 'unknown';
    extractionMethodDisplay.textContent = `Method: ${method} | Confidence: ${(data.overall_confidence * 100).toFixed(1)}%`;
    
    // Show results section
    hideProcessing();
    resultsSection.classList.remove('hidden');
    cameraSection.classList.add('hidden');
    
    // Scroll to results
    setTimeout(() => {
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
    
    console.log('Results displayed successfully');
}

// Populate field with data
function populateField(fieldId, fieldData) {
    const input = document.getElementById(fieldId);
    const confidenceSpan = document.getElementById(`${fieldId}-confidence`);
    
    if (fieldData && fieldData.value) {
        input.value = fieldData.value;
        const conf = (fieldData.confidence * 100).toFixed(0);
        confidenceSpan.textContent = `${conf}% confidence (${fieldData.source})`;
        confidenceSpan.style.color = fieldData.confidence >= 0.9 ? '#10B981' : 
                                    fieldData.confidence >= 0.8 ? '#F59E0B' : '#EF4444';
    } else {
        input.value = '';
        confidenceSpan.textContent = 'Not detected';
        confidenceSpan.style.color = '#9CA3AF';
    }
}

// Save contact
async function saveContact() {
    try {
        const saveBtn = document.getElementById('save-btn');
        const isEditMode = saveBtn.getAttribute('data-edit-mode') === 'true';
        const contactId = saveBtn.getAttribute('data-contact-id');
        
        const contactData = {
            name: nameInput.value,
            organisation: orgInput.value,
            mobile_number: mobileInput.value || null,
            landline_number: landlineInput.value || null,
            email_id: emailInput.value || null,
            designation: designationInput.value || null
        };
        
        // Validate required fields
        if (!contactData.name) {
            showError('Name is required');
            return;
        }
        
        // If editing, include contact ID
        if (isEditMode && contactId) {
            contactData.id = contactId;
        } else {
            // Store pending data for duplicate check
            pendingContactData = contactData;
        }
        
        showProcessing();
        
        const response = await fetch(`${API_BASE_URL}/api/contacts`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(contactData)
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            // Check if it's a duplicate (only for new contacts, not edits)
            if (!isEditMode && response.status === 409 && result.is_duplicate) {
                hideProcessing();
                showDuplicateModal(result.duplicate, contactData);
            } else {
                throw new Error(result.error || 'Failed to save contact');
            }
            return;
        }
        
        hideProcessing();
        
        // If editing, refresh contacts list
        if (isEditMode) {
            showSuccess('Contact updated successfully!');
            // Reset save button
            saveBtn.textContent = '💾 Save Contact';
            saveBtn.removeAttribute('data-edit-mode');
            saveBtn.removeAttribute('data-contact-id');
            // Reload contacts
            await showContactsList();
        } else {
            showSuccess('Contact saved successfully!');
            // Reset after 2 seconds
            setTimeout(() => {
                resetScanner();
            }, 2000);
        }
        
    } catch (error) {
        console.error('Save error:', error);
        showError(error.message || 'Failed to save contact');
        hideProcessing();
    }
}

// Show duplicate modal
function showDuplicateModal(duplicate, newContactData) {
    currentDuplicateInfo = duplicate;
    
    const existing = duplicate.contact;
    const similarity = (duplicate.similarity * 100).toFixed(0);
    const matchReasons = duplicate.match_reasons.join(', ');
    
    duplicateInfo.innerHTML = `
        <div class="duplicate-comparison">
            <div class="existing-contact">
                <h4>Existing Contact:</h4>
                <p><strong>Name:</strong> ${existing.name || 'N/A'}</p>
                <p><strong>Organisation:</strong> ${existing.organisation || 'N/A'}</p>
                <p><strong>Email:</strong> ${existing.email_id || 'N/A'}</p>
                <p><strong>Mobile:</strong> ${existing.mobile_number || 'N/A'}</p>
                <p><strong>Designation:</strong> ${existing.designation || 'N/A'}</p>
            </div>
            <div class="new-contact">
                <h4>New Contact:</h4>
                <p><strong>Name:</strong> ${newContactData.name || 'N/A'}</p>
                <p><strong>Organisation:</strong> ${newContactData.organisation || 'N/A'}</p>
                <p><strong>Email:</strong> ${newContactData.email_id || 'N/A'}</p>
                <p><strong>Mobile:</strong> ${newContactData.mobile_number || 'N/A'}</p>
                <p><strong>Designation:</strong> ${newContactData.designation || 'N/A'}</p>
            </div>
        </div>
        <p class="similarity-info">Similarity: ${similarity}% (matched by: ${matchReasons})</p>
    `;
    
    duplicateModal.classList.remove('hidden');
}

// Overwrite existing contact
async function overwriteContact() {
    if (!currentDuplicateInfo || !pendingContactData) return;
    
    const existingId = currentDuplicateInfo.contact.id;
    const updateData = { 
        ...pendingContactData, 
        id: existingId  // Include ID to update existing contact
    };
    
    try {
        showProcessing();
        duplicateModal.classList.add('hidden');
        
        const response = await fetch(`${API_BASE_URL}/api/contacts`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(updateData)
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Failed to update contact');
        }
        
        hideProcessing();
        showSuccess('Contact updated successfully!');
        
        // Reset after 2 seconds
        setTimeout(() => {
            resetScanner();
        }, 2000);
        
    } catch (error) {
        console.error('Update error:', error);
        showError(error.message || 'Failed to update contact');
        hideProcessing();
    }
}

// Save as new contact (bypass duplicate check)
async function saveAsNewContact() {
    if (!pendingContactData) return;
    
    // Add flag to bypass duplicate check and create a new contact
    const newData = {
        ...pendingContactData,
        _force_new: true  // This tells the backend to skip duplicate detection
    };
    
    try {
        showProcessing();
        duplicateModal.classList.add('hidden');
        
        const response = await fetch(`${API_BASE_URL}/api/contacts`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(newData)
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Failed to save contact');
        }
        
        hideProcessing();
        showSuccess('Contact saved as new!');
        
        setTimeout(() => {
            resetScanner();
        }, 2000);
        
    } catch (error) {
        console.error('Save error:', error);
        showError(error.message || 'Failed to save contact');
        hideProcessing();
    }
}

// Cancel save
function cancelSave() {
    duplicateModal.classList.add('hidden');
    currentDuplicateInfo = null;
    pendingContactData = null; // Clear pending data when cancelled
    hideProcessing();
    // Return to results view so user can modify and try again
}

// Reset scanner - return to homepage
function resetScanner() {
    // Clear fields
    nameInput.value = '';
    orgInput.value = '';
    mobileInput.value = '';
    landlineInput.value = '';
    emailInput.value = '';
    designationInput.value = '';
    rawTextDisplay.textContent = '';
    
    // Reset file input
    fileInput.value = '';
    
    // Reset edit mode
    const saveBtn = document.getElementById('save-btn');
    saveBtn.textContent = '💾 Save Contact';
    saveBtn.removeAttribute('data-edit-mode');
    saveBtn.removeAttribute('data-contact-id');
    
    // Hide sections
    const homepageActions = document.getElementById('homepage-actions');
    resultsSection.classList.add('hidden');
    processingSection.classList.add('hidden');
    cameraSection.classList.add('hidden');
    contactsSection.classList.add('hidden');
    hideSuccess();
    hideError();
    
    // Stop camera
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    stopBorderDetection();
    
    // Show homepage
    homepageActions.classList.remove('hidden');
}

// Reset to camera view
function resetToCamera() {
    hideProcessing();
    resultsSection.classList.add('hidden');
    const homepageActions = document.getElementById('homepage-actions');
    homepageActions.classList.add('hidden');
    cameraSection.classList.remove('hidden');
    if (!stream) {
        initializeCamera();
    }
}

// Show contacts list
async function showContactsList() {
    try {
        const homepageActions = document.getElementById('homepage-actions');
        homepageActions.classList.add('hidden');
        cameraSection.classList.add('hidden');
        resultsSection.classList.add('hidden');
        contactsSection.classList.remove('hidden');
        
        contactsList.innerHTML = '<p>Loading contacts...</p>';
        
        const response = await fetch(`${API_BASE_URL}/api/contacts`);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Failed to load contacts');
        }
        
        if (result.contacts && result.contacts.length > 0) {
            // Store contacts for filtering and use renderContacts to show buttons
            window.allContacts = result.contacts;
            renderContacts(result.contacts);
        } else {
            contactsList.innerHTML = '<p>No contacts saved yet.</p>';
            window.allContacts = [];
        }
        
    } catch (error) {
        console.error('Load contacts error:', error);
        contactsList.innerHTML = `<p class="error">Failed to load contacts: ${error.message}</p>`;
    }
}

// Hide contacts list
function hideContactsList() {
    const homepageActions = document.getElementById('homepage-actions');
    contactsSection.classList.add('hidden');
    cameraSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    homepageActions.classList.remove('hidden');
    contactsSearch.value = ''; // Clear search
}

// Render contacts list
function renderContacts(contacts) {
    if (!contacts || contacts.length === 0) {
        contactsList.innerHTML = '<p>No contacts found.</p>';
        return;
    }
    
    contactsList.innerHTML = contacts.map(contact => `
        <div class="contact-card" data-contact-id="${contact.id}">
            <h3>${contact.name || 'Unknown'}</h3>
            <p><strong>Organisation:</strong> ${contact.organisation || 'N/A'}</p>
            <p><strong>Designation:</strong> ${contact.designation || 'N/A'}</p>
            <p><strong>Email:</strong> ${contact.email_id || 'N/A'}</p>
            <p><strong>Mobile:</strong> ${contact.mobile_number || 'N/A'}</p>
            <p><strong>Landline:</strong> ${contact.landline_number || 'N/A'}</p>
            <p class="contact-meta">Saved: ${new Date(contact.created_at).toLocaleDateString()}</p>
            <div class="contact-actions">
                <button class="btn btn-small btn-primary edit-contact-btn" data-contact-id="${contact.id}">
                    ✏️ Edit
                </button>
                <button class="btn btn-small btn-danger delete-contact-btn" data-contact-id="${contact.id}">
                    🗑️ Delete
                </button>
            </div>
        </div>
    `).join('');
    
    // Add event listeners for edit and delete buttons
    document.querySelectorAll('.edit-contact-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const contactId = e.target.getAttribute('data-contact-id');
            editContact(contactId);
        });
    });
    
    document.querySelectorAll('.delete-contact-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const contactId = e.target.getAttribute('data-contact-id');
            deleteContact(contactId);
        });
    });
}

// Filter contacts by search term
function filterContacts() {
    const searchTerm = contactsSearch.value.toLowerCase().trim();
    
    if (!window.allContacts) {
        return;
    }
    
    if (!searchTerm) {
        renderContacts(window.allContacts);
        return;
    }
    
    const filtered = window.allContacts.filter(contact => {
        const name = (contact.name || '').toLowerCase();
        const email = (contact.email_id || '').toLowerCase();
        const org = (contact.organisation || '').toLowerCase();
        const designation = (contact.designation || '').toLowerCase();
        const mobile = (contact.mobile_number || '').toLowerCase();
        const landline = (contact.landline_number || '').toLowerCase();
        
        return name.includes(searchTerm) ||
               email.includes(searchTerm) ||
               org.includes(searchTerm) ||
               designation.includes(searchTerm) ||
               mobile.includes(searchTerm) ||
               landline.includes(searchTerm);
    });
    
    renderContacts(filtered);
}

// Delete contact
async function deleteContact(contactId) {
    if (!confirm('Are you sure you want to delete this contact? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/contacts/${contactId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Failed to delete contact');
        }
        
        // Remove from local list
        window.allContacts = window.allContacts.filter(c => c.id !== contactId);
        
        // Re-render contacts
        filterContacts();
        
        showSuccess('Contact deleted successfully!');
        
    } catch (error) {
        console.error('Delete error:', error);
        showError(error.message || 'Failed to delete contact');
    }
}

// Edit contact
async function editContact(contactId) {
    const contact = window.allContacts.find(c => c.id === contactId);
    if (!contact) {
        showError('Contact not found');
        return;
    }
    
    // Populate form fields with contact data
    nameInput.value = contact.name || '';
    orgInput.value = contact.organisation || '';
    mobileInput.value = contact.mobile_number || '';
    landlineInput.value = contact.landline_number || '';
    emailInput.value = contact.email_id || '';
    designationInput.value = contact.designation || '';
    
    // Show results section with edit mode
    const homepageActions = document.getElementById('homepage-actions');
    homepageActions.classList.add('hidden');
    contactsSection.classList.add('hidden');
    cameraSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    
    // Change save button text
    const saveBtn = document.getElementById('save-btn');
    const originalText = saveBtn.textContent;
    saveBtn.textContent = '💾 Update Contact';
    saveBtn.setAttribute('data-edit-mode', 'true');
    saveBtn.setAttribute('data-contact-id', contactId);
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Show/hide sections
function showProcessing() {
    cameraSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    processingSection.classList.remove('hidden');
}

function hideProcessing() {
    processingSection.classList.add('hidden');
}

function showSuccess(message) {
    if (message) {
        successMessage.textContent = `✅ ${message}`;
    } else {
        successMessage.textContent = '✅ Contact saved successfully!';
    }
    successMessage.classList.remove('hidden');
    setTimeout(() => {
        hideSuccess();
    }, 3000);
}

function hideSuccess() {
    successMessage.classList.add('hidden');
}

function showError(message) {
    errorText.textContent = message;
    errorMessage.classList.remove('hidden');
}

function hideError() {
    errorMessage.classList.add('hidden');
}

// Utility: Convert file to base64
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            // Remove data URL prefix
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

// Handle page visibility (pause/resume camera)
document.addEventListener('visibilitychange', () => {
    if (document.hidden && stream) {
        // Pause camera when page is hidden
        stream.getTracks().forEach(track => track.stop());
    } else if (!document.hidden && !stream) {
        // Resume camera when page is visible
        initializeCamera();
    }
});
