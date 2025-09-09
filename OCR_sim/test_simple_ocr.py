# test_simple_ocr.py
import cv2
import pytesseract
from PIL import Image
import os

def test_simple_ocr():
    """Test OCR on a sample image."""
    # --- 1. Check Tesseract Path ---
    try:
        # Print Tesseract version to confirm it's found
        print(f"Tesseract version: {pytesseract.get_tesseract_version()}")
    except Exception as e:
        print(f"Error finding Tesseract: {e}")
        # On Windows, you might need to set the path manually:
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        # Uncomment and adjust the path above if needed on Windows.
        return

    # --- 2. Check OpenCV ---
    try:
        print(f"OpenCV version: {cv2.__version__}")
    except Exception as e:
        print(f"Error importing OpenCV: {e}")
        return

    # --- 3. Test with a sample image ---
    # Make sure you have a test image named 'receipt.jpg' in the same directory
    # or change 'test_image.jpg' to the path of your image.
    image_path = 'receipt.jpg'

    if not os.path.exists(image_path):
        print(f"Image file '{image_path}' not found. Please place a test image named 'receipt.jpg' in this directory or modify the script.")
        # Create a simple dummy image with text for testing (requires PIL/Pillow)
        try:
            print("Creating a simple test image...")
            img = Image.new('RGB', (400, 200), color = (73, 109, 137))
            from PIL import ImageDraw, ImageFont
            d = ImageDraw.Draw(img)
            try:
                # Try to use a common font, fallback to default if not found
                font = ImageFont.truetype("arial.ttf", 24)
            except:
                try:
                    font = ImageFont.truetype("DejaVuSans.ttf", 24)
                except:
                     font = ImageFont.load_default()
            d.text((10,10), "Test OCR Image\nLine 2\n12345", fill=(255,255,0), font=font)
            img.save(image_path)
            print(f"Created dummy image: {image_path}")
        except Exception as e:
            print(f"Could not create dummy image: {e}")
            print("Please provide a test image named 'receipt.jpg'.")
            return
    else:
        print(f"Found image: {image_path}")

    # --- 4. Perform OCR ---
    try:
        print("\n--- Performing OCR ---")
        # Method 1: Directly with PIL Image
        print("Method 1: Using PIL Image.open directly...")
        pil_image = Image.open(image_path)
        # Ensure it's in a mode Tesseract can handle (RGB or L for grayscale)
        if pil_image.mode in ('RGBA', 'P'):
            pil_image = pil_image.convert('RGB')
        text1 = pytesseract.image_to_string(pil_image)
        print("Extracted Text (Method 1):")
        print(repr(text1)) # repr() shows newlines and special chars
        print("--- End of Text (Method 1) ---\n")

        # Method 2: Using OpenCV to read and preprocess
        print("Method 2: Using OpenCV preprocessing...")
        opencv_image = cv2.imread(image_path)
        if opencv_image is None:
             print(f"Error: Could not load image with OpenCV from {image_path}")
             return

        # Convert to grayscale (often improves OCR)
        gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
        # Apply threshold to get a binary image (can help)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Use the preprocessed image for OCR
        # Convert OpenCV image (numpy array) back to a PIL Image for pytesseract
        pil_thresh_image = Image.fromarray(thresh)
        text2 = pytesseract.image_to_string(pil_thresh_image)
        print("Extracted Text (Method 2 - Preprocessed):")
        print(repr(text2))
        print("--- End of Text (Method 2) ---\n")

        print("OCR test completed successfully!")

    except Exception as e:
        print(f"Error during OCR processing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_ocr()