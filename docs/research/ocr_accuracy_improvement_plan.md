**System Online.**
**Agent:** ANALYST (V4.0)
**Account:** B (Gemini 1.5 Pro)
**Action:** Executing Research Task.

I have analyzed the provided code, JSON outputs, and constraints. The current implementation of `ocr_processor.py` provides a solid structural foundation, but the extraction logic is too brittle for the noisy reality of thermal receipts, leading to the low confidence scores (~0.48) observed in your logs.

Here is the comprehensive **OCR Accuracy Improvement Plan**.

---

# RESEARCH PLAN: Flash Express OCR Optimization
**Target:** Raspberry Pi 4B (Edge)  
**Date:** 2026-02-11  
**Status:** Phase 7.5 Planning  

## 1. FAILURE ANALYSIS
Based on `scan_*.json` outputs and `ocr_processor.py` logic:

### A. The "Garbage In, Garbage Out" Problem
*   **Observation:** The JSON `raw_text` (inferred) contains artifacts like `FJ cartos Johnsen` instead of `Carlos Johnson`.
*   **Cause:** The **Denoising** (`fastNlMeansDenoising`) parameters (`h=10`) might be too aggressive for faded thermal text, blurring thin characters. Conversely, the **Adaptive Threshold** (`blockSize=11`) is very small, likely amplifying paper grain noise.
*   **Impact:** Tesseract sees broken characters ("c" becomes "o", "l" becomes "i"), lowering confidence.

### B. The Regex Rigidity
*   **Observation:** `buyerAddress` extraction failed in scan `...314` ("0 EM visit oy..."). In scan `...099`, it captured the name *into* the address field.
*   **Cause:** The regex `r'(\d+[\w\s]+St(?:reet)?...'` expects a specific format ("St", "Brgy"). Flash Express receipts often omit "St" or use abbreviations.
*   **Layout Shift:** The code treats the OCR output as a single string. If Tesseract reads the "Seller" column *before* the "Buyer" column (due to column segmentation failure), the regex looks in the wrong place.

### C. Missing Fields
*   **Observation:** `rider_id` and `order_id` are frequently null.
*   **Cause:** These fields are often in small print or near the noisy edges of the receipt (printer margins).

---

## 2. OCR ENGINE EVALUATION (Edge Focused)

| Engine | Pi 4B Performance | Accuracy | Verdict |
| :--- | :--- | :--- | :--- |
| **Tesseract 5.x (Current)** | **Fast (<2s)** | Moderate | **KEEP.** Best trade-off for Pi CPU. Requires better preprocessing. |
| **PaddleOCR (Lite)** | Slow (~5-8s) | High | **REJECT.** Too heavy for "interactive" scanning on Pi CPU. Good for offline fallback only. |
| **EasyOCR** | Very Slow (>10s) | High | **REJECT.** PyTorch overhead is too high for Pi 4B RAM (4GB). |
| **ZBar / PyZbar** | Instant (<0.1s) | N/A | **ADD.** Dedicated barcode/QR scanner. Why OCR the tracking ID if there is a barcode? |

**Recommendation:** Optimize Tesseract usage (PSM modes) + Add `pyzbar` for 100% accurate Tracking/Order IDs via barcodes, leaving OCR to just handle Name/Address.

---

## 3. PREPROCESSING PIPELINE UPGRADE

Current pipeline is linear. We propose a **Multi-Branch Preprocessing** strategy.

### Step A: Dynamic Binarization
Instead of one threshold, generate two versions of the image:
1.  **Heavy Denoise:** For large text (Tracking ID).
2.  **Light Denoise:** For small text (Address/Items).
*Run Tesseract on both? No, too slow. Run on "Light" first, check confidence.*

### Step B: The "Orange Killer" Refinement
The current HSV mask `[10, 100, 100]` is risky.
*   **Proposal:** Use **CLAHE** (Contrast Limited Adaptive Histogram Equalization) on the Value channel (HSV) *before* thresholding. This boosts the dark text against the orange background without needing to color-mask it explicitly.

### Step C: ROI (Region of Interest) Cropping
Don't OCR the whole image at once.
1.  **Anchor Search:** Find "Flash Express" logo or Barcode.
2.  **Coordinate Mapping:** Based on the anchor, we know "Buyer" is roughly at `[y+200:y+400, x:x_mid]`.
3.  **Crop & OCR:** Send only the relevant slice to Tesseract. This increases PSM (Page Segmentation Mode) accuracy significantly.

---

## 4. POST-PROCESSING & PARSING STRATEGY

### A. Hybrid Barcode + OCR
Most extraction failures are on IDs.
*   **Action:** Integrate `pyzbar`.
*   **Logic:**
    ```python
    decoded = pyzbar.decode(image)
    if decoded:
        fields['tracking_id'] = decoded[0].data.decode('utf-8')
    else:
        # Fallback to OCR regex
    ```

### B. Fuzzy Anchoring
Regex is strict. Use `fuzzywuzzy` (or simple Levenshtein distance) to find headers.
*   Instead of `re.search(r'Buyer')`, find line most similar to "Buyer Details".
*   Use the *line index* to extract the *next 3 lines* as the address, ignoring format validation initially.

### C. Address Block Logic
Philippine addresses are unstructured.
*   **Old Logic:** Regex looking for "St", "Brgy".
*   **New Logic:**
    1.  Find "Buyer" header.
    2.  Find "Seller" header (usually right column or below).
    3.  Extract text *between* those headers.
    4.  Filter out phone numbers (regex `09\d{9}`).
    5.  Remainder is the Address + Name.

---

## 5. MODULARITY & ARCHITECTURE

Refactor `ocr_processor.py` into a **Pipeline Pattern**.

```python
class OCRPipeline:
    def process(self, image):
        # 1. Image Enhancement
        clean_img = self.preprocessor.enhance(image)
        
        # 2. Barcode Scan (Fast path)
        ids = self.barcode_scanner.scan(clean_img)
        
        # 3. Layout Analysis (Get boxes, not just text)
        layout_data = self.ocr_engine.get_boxes(clean_img)
        
        # 4. Spatial Extraction (Extract by coordinates)
        fields = self.extractor.extract_from_layout(layout_data, ids)
        
        return fields
```
This allows swapping Tesseract for Paddle later without rewriting the extraction logic.

---

## 6. PERFORMANCE TARGETS

| Metric | Current Est. | Target | Strategy |
| :--- | :--- | :--- | :--- |
| **Accuracy (Tracking ID)** | 60% | **99.9%** | Switch to Barcode (PyZbar). |
| **Accuracy (Address)** | 30% | **85%** | ROI Cropping + Spatial Logic. |
| **Processing Time** | ~2.5s | **< 1.5s** | ROI limits pixel count for OCR. |
| **Confidence Score** | ~0.45 | **> 0.75** | CLAHE + Better Binarization. |

---

## 7. TEST SET METHODOLOGY

We cannot improve what we cannot measure.

1.  **Dataset:** We need 20 diverse images (Good lighting, bad lighting, crumpled, angled).
2.  **Annotation:** Create `tests/ocr_ground_truth.json`:
    ```json
    {
      "receipt_01.jpg": {
        "tracking_id": "FE123...",
        "buyer_address": "Block 5..."
      }
    }
    ```
3.  **Harness:** A script `tests/benchmark_ocr.py` that runs the processor against these images and calculates:
    *   **Exact Match Rate:** % of fields matching perfectly.
    *   **Levenshtein Distance:** How close the address is (allows for minor typos).

---

## 8. PHASED IMPLEMENTATION ROADMAP

### Phase A: The "Low Hanging Fruit" (Sprint 1)
1.  **Install `pyzbar`** and `libzbar0`.
2.  Update `ocr_processor.py` to check for barcodes first.
3.  **Result:** Instant fix for Tracking/Order IDs.

### Phase B: Preprocessing Tuning (Sprint 1-2)
1.  Implement **CLAHE** contrast enhancement.
2.  Create a "Debug Mode" in the dashboard to view the *processed* binary image (to see what Tesseract sees).
3.  Tune `adaptiveThreshold` block size (try 11, 21, 31).

### Phase C: Spatial Extraction (Sprint 2)
1.  Switch Tesseract to output `image_to_data` (bounding boxes).
2.  Implement "Zone Extraction" (e.g., if text is in bottom-right 20% of width, it's likely the timestamp or price).

---

### ACTIONABLE NEXT STEP
I recommend starting **Phase A** immediately.

**Analyst Output:**
- **Spec Created:** `docs/research/ocr_accuracy_improvement_plan.md`
- **Next Step:** Pass this plan to the **Implementer** to execute Phase A (Barcode Integration).