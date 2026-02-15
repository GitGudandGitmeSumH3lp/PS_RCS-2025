"""Test script to validate OCR improvements on Flash Express receipts.

This script tests the fixed OCR processor against the training set.
"""
import cv2
import json
import sys
from pathlib import Path

# Add fixed modules to path
sys.path.insert(0, '/home/claude')

from ocr_processor_fixed import FlashExpressOCR


def load_ground_truth(json_path: str) -> dict:
    """Load ground truth data from JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def test_image(ocr_processor, image_path: str, expected: dict) -> dict:
    """Test OCR on a single image and compare with ground truth."""
    # Load image
    frame = cv2.imread(image_path)
    if frame is None:
        return {
            'success': False,
            'error': f"Failed to load image: {image_path}"
        }
    
    # Process with OCR
    result = ocr_processor.process_frame(frame)
    
    # Compare with ground truth
    filename = Path(image_path).name
    
    comparisons = {
        'tracking_id': (result.get('tracking_id'), expected.get('tracking_id')),
        'buyer_name': (result.get('buyer_name'), expected.get('buyer_name')),
        'address': (result.get('buyer_address'), expected.get('address')),
        'weight': (f"{result.get('weight_g')}g" if result.get('weight_g') else None, 
                   expected.get('weight')),
        'quantity': (str(result.get('quantity')) if result.get('quantity') else None, 
                     expected.get('quantity'))
    }
    
    # Check accuracy
    matches = {}
    for field, (actual, expected_val) in comparisons.items():
        if actual and expected_val:
            matches[field] = actual == expected_val
        else:
            matches[field] = actual == expected_val  # Both None = match
    
    return {
        'success': True,
        'filename': filename,
        'comparisons': comparisons,
        'matches': matches,
        'confidence': result.get('confidence', 0.0),
        'processing_time_ms': result.get('processing_time_ms', 0)
    }


def main():
    """Run tests on all training images."""
    # Initialize OCR processor
    print("Initializing OCR processor...")
    ocr = FlashExpressOCR(debug_align=False)
    
    # Load ground truth
    print("Loading ground truth...")
    ground_truth = load_ground_truth('/mnt/user-data/uploads/ground_truth.json')
    
    # Test each image
    print("\n" + "="*60)
    print("TESTING OCR WITH FIXES")
    print("="*60 + "\n")
    
    results = []
    total_matches = {
        'tracking_id': 0,
        'buyer_name': 0,
        'address': 0,
        'weight': 0,
        'quantity': 0
    }
    
    for image_file, expected in ground_truth.items():
        image_path = f"/mnt/user-data/uploads/{image_file}"
        
        print(f"Processing {image_file}...")
        result = test_image(ocr, image_path, expected)
        
        if not result['success']:
            print(f"  ERROR: {result['error']}")
            continue
        
        # Print results
        matches = result['matches']
        for field, match in matches.items():
            symbol = "✓" if match else "✗"
            actual, expected_val = result['comparisons'][field]
            print(f"  {field:12s}: {actual} (expected: {expected_val}) {symbol}")
            
            if match:
                total_matches[field] += 1
        
        print(f"  Confidence:  {result['confidence']*100:.2f}%")
        print(f"  Time:        {result['processing_time_ms']}ms")
        print()
        
        results.append(result)
    
    # Print summary
    print("="*60)
    print("ACCURACY SUMMARY")
    print("="*60)
    
    num_images = len(results)
    for field, count in total_matches.items():
        accuracy = (count / num_images) * 100 if num_images > 0 else 0
        print(f"{field:12s}: {count}/{num_images} ({accuracy:.1f}%)")
    
    # Calculate averages
    avg_conf = sum(r['confidence'] for r in results) / len(results) if results else 0
    avg_time = sum(r['processing_time_ms'] for r in results) / len(results) if results else 0
    
    print(f"\nAvg Confidence: {avg_conf*100:.2f}%")
    print(f"Avg Time:       {avg_time:.0f}ms")


if __name__ == "__main__":
    main()
