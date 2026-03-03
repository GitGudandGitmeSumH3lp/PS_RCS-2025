#!/usr/bin/env python3
"""Test zonal OCR against ground truth."""

import json
import cv2
from pathlib import Path
from src.services.ocr_processor import FlashExpressOCR

def test_zonal_ocr():
    """Run zonal OCR on test images and compare to ground truth."""
    
    # Load ground truth
    with open('ground_truth.json', 'r') as f:
        ground_truth = json.load(f)
    
    # Initialize OCR
    ocr = FlashExpressOCR()
    
    # Test each image
    results = []
    for img_name in sorted(ground_truth.keys()):
        print(f"\nProcessing {img_name}...")
        
        # Load image
        img_path = Path('OCR_sim/images') / img_name
        if not img_path.exists():
            print(f"  ❌ Image not found: {img_path}")
            continue
        
        frame = cv2.imread(str(img_path))
        
        # Process
        result = ocr.process_frame(frame)
        fields = result['fields']
        
        # Compare to ground truth
        gt = ground_truth[img_name]
        
        print(f"  Tracking ID: {fields['tracking_id']} "
              f"(expected: {gt['tracking_id']}) "
              f"{'✓' if fields['tracking_id'] == gt['tracking_id'] else '✗'}")
        
        print(f"  Buyer Name:  {fields['buyer_name']} "
              f"(expected: {gt['buyer_name']}) "
              f"{'✓' if fields['buyer_name'] == gt['buyer_name'] else '✗'}")
        
        print(f"  Weight:      {fields['weight_g']}g "
              f"(expected: {gt['weight']}) "
              f"{'✓' if str(fields['weight_g']) + 'g' == gt['weight'] else '✗'}")
        
        print(f"  Quantity:    {fields['quantity']} "
              f"(expected: {gt['quantity']}) "
              f"{'✓' if str(fields['quantity']) == gt['quantity'] else '✗'}")
        
        print(f"  Confidence:  {fields['confidence']:.2%}")
        print(f"  Time:        {result['processing_time_ms']}ms")
        
        results.append({
            'image': img_name,
            'result': result,
            'ground_truth': gt
        })
    
    # Calculate accuracy
    print("\n" + "="*60)
    print("ACCURACY SUMMARY")
    print("="*60)
    
    total = len(results)
    tracking_correct = sum(1 for r in results 
                          if r['result']['fields']['tracking_id'] == r['ground_truth']['tracking_id'])
    name_correct = sum(1 for r in results 
                      if r['result']['fields']['buyer_name'] == r['ground_truth']['buyer_name'])
    weight_correct = sum(1 for r in results 
                        if str(r['result']['fields']['weight_g']) + 'g' == r['ground_truth']['weight'])
    qty_correct = sum(1 for r in results 
                     if str(r['result']['fields']['quantity']) == r['ground_truth']['quantity'])
    
    print(f"Tracking ID: {tracking_correct}/{total} ({100*tracking_correct/total:.1f}%)")
    print(f"Buyer Name:  {name_correct}/{total} ({100*name_correct/total:.1f}%)")
    print(f"Weight:      {weight_correct}/{total} ({100*weight_correct/total:.1f}%)")
    print(f"Quantity:    {qty_correct}/{total} ({100*qty_correct/total:.1f}%)")
    
    avg_conf = sum(r['result']['fields']['confidence'] for r in results) / total
    avg_time = sum(r['result']['processing_time_ms'] for r in results) / total
    
    print(f"\nAvg Confidence: {avg_conf:.2%}")
    print(f"Avg Time:       {avg_time:.0f}ms")

if __name__ == '__main__':
    test_zonal_ocr()