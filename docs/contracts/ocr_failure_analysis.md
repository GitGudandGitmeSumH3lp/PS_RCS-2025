# FEATURE SPEC: OCR Failure Analysis & Correction Plan
**Date:** 2026-02-14
**Status:** **CRITICAL FIX NEEDED**

## 1. THE FINDINGS (Comparison to Ground Truth)

I have compared your raw JSON outputs against the Ground Truth dataset we just created. The current system is operating at a **Critical Failure** level for key fields (Name/Address) but shows promise in barcode/tracking ID detection.

| Field | Success Rate | Primary Failure Mode | Example (Ground Truth vs. Actual) |
| :--- | :--- | :--- | :--- |
| **Tracking ID** | **85% (High)** | Digit Confusion | **GT:** FE528... **Actual:** FE**6**28... (5 read as 6) |
| **Buyer Name** | **0% (Fail)** | Anchor Miss / Noise | **GT:** Carlos Johnson **Actual:** `null` or "NO Garlos Johnsen" |
| **Address** | **15% (Low)** | Layout Bleed / Garbage | **GT:** 13 Kamuning Rd... **Actual:** "GF istrict City Zp cote..." |
| **Weight** | **20% (Low)** | Regex Strictness | **GT:** 6872g **Actual:** `null` |
| **Quantity** | **60% (Med)** | Hallucination | **GT:** 13 **Actual:** 18 (James Flores) |

---

## 2. DETAILED FAILURE PATTERNS

### A. The "Column Bleed" Issue (Address Corruption)
*   **Symptom:** The OCR is reading the pre-printed headers ("District", "City", "Zip Code") *into* the address field.
*   **Evidence:** In the Jane Davis scan (`scan...1034.json`), the address returns as `"istrict City Zp cote"`.
*   **Cause:** The OCR engine reads straight across the page. It sees the small text headers below the address line and merges them.
*   **Fix:** We need **Layout Analysis** or **Zonal OCR**. We must crop the specific box where the address lives before reading text.

### B. The "Anchor" Failure (Missing Names)
*   **Symptom:** Buyer Name is consistently `null` or garbage.
*   **Evidence:**
    *   Carlos scan: Reads "NO Garlos Johnsen". The "C" in Carlos was read as "G" or "NO".
    *   Other scans: The system returns `null` because it likely looks for a keyword like "Buyer:" which might be obscured or reading as "BUYER" vertical text on the left sidebar (black strip).
*   **Cause:** The black vertical sidebar on the left (saying "BUYER") is likely interfering with line segmentation.

### C. Visual Noise & Preprocessing
*   **Symptom:** "Brgy" is read as "Bray" or "Big?". "Silang" read as "Stang".
*   **Cause:** The thermal print on receipts is grainy. Standard binarization (turning image to black/white) might be destroying the dot-matrix-style text.

---

## 3. PROPOSED ARCHITECTURAL CHANGES (For Architect)

To fix this, we need to move from "Full Page OCR" to "Region-Based OCR".

### New Pipeline Logic:
1.  **Detect Anchors:** Find the solid horizontal lines or the black "BUYER" / "SELLER" sidebars.
2.  **Crop Regions:**
    *   **Region A (Top):** Barcode & Tracking ID.
    *   **Region B (Middle Left):** Buyer Details (Name/Address).
    *   **Region C (Bottom):** Product Details (Weight/Qty).
3.  **Pre-process Separately:**
    *   Region A needs high contrast for barcodes.
    *   Region B needs "dilation" to connect the dots in the thermal font.

### Immediate Action Items for Architect
1.  **Implement Zonal Cropping:** Don't OCR the whole image at once.
2.  **Refine Regex:**
    *   Weight regex is likely too strict (e.g., expecting "kg" but seeing "g").
    *   Address cleaning needs to strip out known headers like "District", "City", "Province".

---

## 4. NEXT STEPS

I am passing this analysis to the Architect. The goal is to update the processing pipeline to specifically handle the **Flash Express Label Layout**.

**Next Agent:** Architect
**Task:** Design the `FlashExpressParser` class with region-based logic.