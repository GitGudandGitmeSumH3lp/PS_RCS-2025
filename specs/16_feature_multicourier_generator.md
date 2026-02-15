# FEATURE SPEC: Multi-Courier Synthetic Label Generator (v2.0)
**Date:** 2025-05-15
**Status:** Feasible

## 1. THE VISION
*   **User Story:** As a Developer training an OCR model, I want to generate synthetic shipping labels for multiple couriers (Flash Express, Shopee SPX) with perfect "Ground Truth" JSON data, so that I can validate the accuracy of my OCR pipeline without relying on sensitive real-world data.
*   **Success Metrics:**
    *   Support for 2 distinct templates: Flash Express (Legacy) and Shopee SPX (New).
    *   100% match between the text on the generated image and the exported JSON file.
    *   Ability to batch generate 50+ unique labels in one click.
    *   Shopee template strictly follows the "Types of shipping documents" PDF guidelines (Hidden contact numbers, specific tagline).

## 2. FEASIBILITY CHECK
*   **System Constraints:** ✅ Passed. Pure Client-Side implementation (HTML5/JS).
*   **New Libraries Needed:** 
    *   `JSZip` (Recommended for batch downloading images + JSON in one go).
    *   Existing: `html2canvas`, `jspdf`, `qrcode.js`, `JsBarcode`.
*   **Risk Level:** Low. The complexity lies in CSS layout accuracy, not logic.

## 3. ARCHITECTURE & DATA STRUCTURE

### 3.1 The Courier Configuration Schema
Instead of hardcoding logic, we will use a Strategy Pattern. Each courier is a config object.

```javascript
/* src/couriers/types.js (Conceptual) */
const CourierConfig = {
    id: "shopee_spx",
    name: "Shopee Xpress (SPX)",
    branding: {
        logoUrl: "assets/spx_logo.png",
        primaryColor: "#EE4D2D",
        tagline: "Ang Dali-Dali sa Shopee with On-Time Delivery Guarantee" // Per PDF
    },
    generators: {
        trackingNumber: () => "SPX" + ..., 
        orderId: () => ...,
        sortCode: () => ..., // e.g. "11-0902-3A-06"
        routeCode: () => ... // e.g. "D2-27-1"
    },
    layout: {
        templateId: "shopee-standard-v1",
        cssClass: "label-spx"
    }
};
```

### 3.2 Ground Truth JSON Format
Every generated label must output a corresponding JSON file for OCR validation.

```json
{
  "meta": {
    "courier": "Shopee Xpress",
    "generated_at": "2025-10-20T10:00:00Z",
    "template_version": "v1.0"
  },
  "fields": {
    "tracking_number": "SPX123456789",
    "order_id": "240510SPX999",
    "sort_code": "11-0902-3A-06",
    "route_code": "PAT-C",
    "buyer": {
      "name": "John Doe",
      "address": "Unit 5, 2nd Floor, ABC Bldg...",
      "district": "Sampaloc",
      "city": "Manila",
      "zip": "1008"
    },
    "seller": {
      "name": "Mega Shop",
      "address": "..." // Phone number hidden per PDF rules
    },
    "details": {
      "weight_kg": 0.5,
      "cod_amount": 150.00,
      "product_description": "Wireless Mouse x1"
    }
  }
}
```

## 4. ATOMIC TASKS (The Roadmap)

### Phase 1: Refactoring Core Engine
*   [ ] **Task 1.1:** Separate `app.js` into `LabelEngine.js` (logic) and `LabelRenderer.js` (DOM manipulation).
*   [ ] **Task 1.2:** Implement `CourierRegistry` to manage switching between Flash and Shopee.

### Phase 2: Shopee SPX Implementation
*   [ ] **Task 2.1:** Create `couriers/shopee.js`. Implement data generators specifically for SPX formats (Sorting codes like `D2-27-1`).
*   [ ] **Task 2.2:** Build HTML Template for Shopee.
    *   *Constraint:* Must include the specific branding text from PDF.
    *   *Constraint:* Must hide phone numbers (Privacy Act compliance from PDF).
*   [ ] **Task 2.3:** Add CSS for Shopee (Orange theme, distinct borders).

### Phase 3: Features & Polish
*   [ ] **Task 3.1:** Implement "Batch Mode" with `JSZip` integration.
    *   *Action:* User clicks "Generate 50". System generates 50 Images + 50 JSON files -> Zips them -> Downloads `training_data.zip`.
*   [ ] **Task 3.2:** Dictionary Extractor.
    *   *Feature:* A utility function to dump all currently used arrays (Barangays, Streets) into a `dictionary.json` file for the Python backend.

## 5. INTERFACE SKETCHES

**Module:** `LabelEngine`

*   `switchCourier(courierId)`
    *   Updates the `currentConfig`.
    *   Triggers UI refresh of the specific input fields (some couriers might need different inputs).
*   `generateBatch(count)`
    *   Loop `count` times.
    *   Call `config.generators.*`.
    *   Render to hidden DOM.
    *   Canvas capture.
    *   Add to Zip.

**Module:** `ShopeeTemplate (HTML Structure)`

```html
<!-- Based on PDF Visuals -->
<div class="label-container spx-theme">
  <div class="header">
    <img src="spx_logo.png">
    <div class="sort-code-large">{{sort_code}}</div> <!-- e.g., PAT-C -->
  </div>
  <div class="barcodes">
    <!-- Top: Order ID, Bottom: Tracking -->
  </div>
  <div class="address-grid">
    <!-- Seller (Top Left), Buyer (Bottom) -->
    <!-- Specific "POD" (Proof of Delivery) area bottom right -->
  </div>
  <div class="footer-tagline">
    Ang Dali-Dali sa Shopee with On-Time Delivery Guarantee
  </div>
</div>
```

## 6. OPEN QUESTIONS
1.  **Barcode Format:** The PDF shows multiple barcodes. Usually, Shopee uses Code 128 for Order ID and Tracking. Shall we assume Code 128 for all? (Assumption: Yes).
2.  **QR Codes:** The PDF shows QR codes on some layouts (e.g., J&T integration), but standard SPX AWB in the screenshot focuses on Barcodes. We will include a QR code for the Tracking Number as a fallback unless specified otherwise.

---

## POST-ACTION REPORT
✅ **Spec Created:** `specs/feature_multicourier_generator.md`
📋 **Next Step:** Architect to design the directory structure and class interactions.
👉 **Next Agent:** Architect