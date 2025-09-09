#!/usr/bin/env python3
"""
Script to diagnose and fix OpenCV issues
"""

def test_opencv():
    """Test OpenCV installation"""
    try:
        import cv2
        print(f" OpenCV imported successfully")
        print(f"OpenCV version: {cv2.__version__}")
        
        # Test specific attributes
        if hasattr(cv2, 'MORPH_OPENING'):
            print(" MORPH_OPENING available")
        elif hasattr(cv2, 'MORPH_OPEN'):
            print("  Using MORPH_OPEN instead of MORPH_OPENING")
        else:
            print(" Morphological operations not available")
        
        # Test basic functionality
        import numpy as np
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        gray = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)
        print("✅ Basic OpenCV operations work")
        
        return True
        
    except ImportError as e:
        print(f" OpenCV import failed: {e}")
        return False
    except Exception as e:
        print(f" OpenCV test failed: {e}")
        return False

def test_tesseract():
    """Test Tesseract installation"""
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f" Tesseract version: {version}")
        return True
    except Exception as e:
        print(f" Tesseract test failed: {e}")
        print("Please install Tesseract OCR:")
        print("Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        print("macOS: brew install tesseract")
        print("Linux: sudo apt-get install tesseract-ocr")
        return False

def fix_installation():
    """Provide fix suggestions"""
    print("\n=== Fix Suggestions ===")
    print("1. Uninstall current OpenCV:")
    print("   pip uninstall opencv-python opencv-python-headless")
    print("\n2. Reinstall OpenCV:")
    print("   pip install opencv-python-headless==4.8.1.78")
    print("\n3. If still having issues, try:")
    print("   pip install opencv-contrib-python-headless")
    print("\n4. For Tesseract issues on Windows, add to your ocr.py:")
    print("   pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'")

if __name__ == "__main__":
    print("=== OpenCV & Tesseract Diagnostic ===\n")
    
    opencv_ok = test_opencv()
    tesseract_ok = test_tesseract()
    
    if not opencv_ok or not tesseract_ok:
        fix_installation()
    else:
        print("\n All dependencies are working correctly!")
        print("You can now run: python ocr.py") 