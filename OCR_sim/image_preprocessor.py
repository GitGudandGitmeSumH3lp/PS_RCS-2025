# image_preprocessor.py (V3 - Enhanced for Shipping Labels)

import cv2
import numpy as np
from PIL import Image, ImageEnhance
import os

def enhance_contrast_and_brightness(image, contrast=1.2, brightness=10):
    """Enhance contrast and brightness for better OCR accuracy"""
    # Convert to float to prevent overflow
    enhanced = cv2.convertScaleAbs(image, alpha=contrast, beta=brightness)
    return enhanced

def remove_noise(image, kernel_size=3):
    """Remove noise using morphological operations"""
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    # Opening (erosion followed by dilation) to remove noise
    opened = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)
    return opened

def detect_text_regions(image):
    """Detect potential text regions using MSER or contour analysis"""
    # Create MSER detector
    mser = cv2.MSER_create(
        _delta=5,
        _min_area=100,
        _max_area=5000,
        _max_variation=0.25,
        _min_diversity=0.2
    )
    
    regions, _ = mser.detectRegions(image)
    
    # Create mask for text regions
    mask = np.zeros_like(image)
    for region in regions:
        # Create bounding box for each region
        x, y, w, h = cv2.boundingRect(region.reshape(-1, 1, 2))
        cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
    
    return mask

def pipeline_for_shipping_label_ocr(image_path):
    """
    Enhanced preprocessing pipeline specifically designed for shipping labels
    with multiple text regions, barcodes, and varying text sizes.
    """
    try:
        # 1. Read the image
        original_image = cv2.imread(image_path)
        if original_image is None:
            raise ValueError(f"Could not read image from path: {image_path}")

        # 2. Initial resize for processing speed while maintaining quality
        h, w, _ = original_image.shape
        
        # For shipping labels, maintain higher resolution for small text
        if w > 1200:
            target_w = 1200
            scale = target_w / w
            target_h = int(h * scale)
            resized = cv2.resize(original_image, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
        else:
            resized = original_image.copy()

        # 3. Convert to grayscale
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        # 4. Enhanced contrast and brightness
        enhanced = enhance_contrast_and_brightness(gray, contrast=1.3, brightness=15)

        # 5. Noise reduction with gentle blur
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)

        # 6. Perspective correction (improved for shipping labels)
        corrected_image = apply_perspective_correction(denoised, resized)

        # 7. Adaptive thresholding with multiple methods
        # Method 1: Adaptive Gaussian (good for varied lighting)
        thresh1 = cv2.adaptiveThreshold(corrected_image, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8)
        
        # Method 2: OTSU thresholding (good for clear text)
        _, thresh2 = cv2.threshold(corrected_image, 0, 255, 
            cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Combine both methods for better results
        combined_thresh = cv2.bitwise_and(thresh1, thresh2)

        # 8. Morphological operations to clean up text
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        final_image = cv2.morphologyEx(combined_thresh, cv2.MORPH_CLOSE, kernel)
        
        # 9. Final cleanup - remove small noise
        final_image = remove_noise(final_image, kernel_size=2)

        print(f"INFO: Enhanced preprocessing applied to {os.path.basename(image_path)}")
        return Image.fromarray(final_image)

    except Exception as e:
        import traceback
        print(f"ERROR in enhanced image_preprocessor for {os.path.basename(image_path)}:")
        traceback.print_exc()
        # Return original grayscale as fallback
        try:
            gray_fallback = cv2.cvtColor(cv2.imread(image_path), cv2.COLOR_BGR2GRAY)
            return Image.fromarray(gray_fallback)
        except:
            return Image.fromarray(np.zeros((100, 100), dtype=np.uint8))

def apply_perspective_correction(gray_image, original_color):
    """
    Improved perspective correction specifically for shipping labels
    """
    try:
        # Use bilateral filter for edge detection preprocessing
        filtered = cv2.bilateralFilter(gray_image, 11, 17, 17)
        
        # Multiple edge detection methods
        edges1 = cv2.Canny(filtered, 30, 100)
        edges2 = cv2.Canny(filtered, 50, 150)
        edges = cv2.bitwise_or(edges1, edges2)
        
        # Morphological closing to connect broken edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(edges.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

        document_contour = None
        
        # Look for rectangular contours (shipping labels are typically rectangular)
        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.015 * peri, True)
            
            if len(approx) == 4:
                # Check if the contour is large enough to be the document
                area = cv2.contourArea(contour)
                image_area = gray_image.shape[0] * gray_image.shape[1]
                
                if area > image_area * 0.1:  # At least 10% of image area
                    document_contour = approx
                    break

        if document_contour is not None:
            # Apply perspective correction
            pts = document_contour.reshape(4, 2)
            rect = order_points(pts)
            
            # Calculate dimensions of the corrected image
            (tl, tr, br, bl) = rect
            
            widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
            widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))

            heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
            heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))

            # Destination points for perspective transform
            dst = np.array([
                [0, 0],
                [maxWidth - 1, 0],
                [maxWidth - 1, maxHeight - 1],
                [0, maxHeight - 1]], dtype="float32")

            # Apply perspective transform
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(gray_image, M, (maxWidth, maxHeight))
            
            print("INFO: Perspective correction successfully applied")
            return warped
        else:
            print("INFO: No suitable document contour found, using original image")
            return gray_image
            
    except Exception as e:
        print(f"WARNING: Perspective correction failed: {str(e)}")
        return gray_image

def order_points(pts):
    """Order points in top-left, top-right, bottom-right, bottom-left order"""
    rect = np.zeros((4, 2), dtype="float32")
    
    # Sum and difference method to find corners
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # Top-left
    rect[2] = pts[np.argmax(s)]  # Bottom-right
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # Top-right
    rect[3] = pts[np.argmax(diff)]  # Bottom-left
    
    return rect

# Alternative processing function for difficult images
def pipeline_for_ocr_robust_fallback(image_path):
    """
    Fallback pipeline with more aggressive preprocessing
    """
    try:
        original_image = cv2.imread(image_path)
        if original_image is None:
            raise ValueError(f"Could not read image from path: {image_path}")

        # Convert to grayscale
        gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Strong bilateral filtering
        filtered = cv2.bilateralFilter(enhanced, 15, 80, 80)
        
        # Multiple thresholding approaches
        _, otsu_thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        adaptive_thresh = cv2.adaptiveThreshold(filtered, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
                                               cv2.THRESH_BINARY, 21, 10)
        
        # Combine thresholding results
        combined = cv2.bitwise_and(otsu_thresh, adaptive_thresh)
        
        return Image.fromarray(combined)
        
    except Exception as e:
        print(f"ERROR in fallback preprocessor: {str(e)}")
        return Image.fromarray(np.zeros((100, 100), dtype=np.uint8))

# Main function for external use
def pipeline_for_ocr(image_path):
    """Main preprocessing function - tries enhanced method first, falls back if needed"""
    try:
        return pipeline_for_shipping_label_ocr(image_path)
    except Exception as e:
        print(f"Enhanced preprocessing failed, trying fallback method: {str(e)}")
        return pipeline_for_ocr_robust_fallback(image_path)