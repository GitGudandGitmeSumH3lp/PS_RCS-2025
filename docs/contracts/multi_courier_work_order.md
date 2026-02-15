# WORK ORDER FOR IMPLEMENTER

**Target Directory:** `parcel_generator/`
**Contract Reference:** `CONTRACT_MULTI_COURIER_GENERATOR.md` v1.0
**Estimated Effort:** 4-5 weeks (phased implementation)

---

## 🎯 MISSION BRIEF

Transform the existing Flash Express label generator into a modular, multi-courier system supporting Flash Express and Shopee SPX, with ground truth export capabilities for OCR training. The system must be highly extensible to accommodate future courier additions.

---

## 📋 STRICT CONSTRAINTS (NON-NEGOTIABLE)

### Architecture Constraints

1. **Vanilla JavaScript Only** - No frameworks (React, Vue, Angular)
2. **ES6+ Standards** - Use modern JavaScript features (classes, modules, async/await)
3. **CDN Libraries Only** - All external libraries via CDN (no npm/webpack)
4. **Modular Structure** - Follow the specified directory structure exactly
5. **Interface Contracts** - All classes must implement interfaces defined in contract

### Performance Constraints

1. **Single Label Generation:** < 500ms
2. **Batch of 10 Labels:** < 5 seconds
3. **Batch of 100 Labels:** < 60 seconds
4. **Image Capture:** < 2 seconds per label
5. **Memory Limit:** Max 200 concurrent labels in DOM

### Code Quality Constraints

1. **JSDoc Comments:** All functions, classes, and methods must have JSDoc
2. **Error Handling:** Use try-catch for all async operations
3. **Validation:** Validate all user inputs and generated data
4. **No Console Logs:** Remove all debug console.log statements
5. **Browser Support:** Chrome 90+, Firefox 88+, Safari 14+

---

## 🏗️ REQUIRED DIRECTORY STRUCTURE

Create the following directory structure exactly as specified:

```
parcel_generator/
├── index.html                          (Enhanced UI with parcel theme)
├── styles.css                          (White enterprise + parcel styling)
├── app.js                              (Main application controller)
├── couriers/
│   ├── flash-express.js               (Flash Express config - refactor from existing)
│   ├── shopee-spx.js                  (Shopee SPX config - NEW)
│   └── courier-template.js            (Template for future couriers)
├── core/
│   ├── label-engine.js                (Core generation logic - NEW)
│   ├── label-renderer.js              (DOM rendering & image capture - NEW)
│   ├── courier-registry.js            (Courier management - NEW)
│   └── ground-truth-exporter.js       (JSON export & ZIP - NEW)
├── utils/
│   ├── data-generators.js             (Shared utilities - refactor from existing)
│   ├── dictionary-extractor.js        (Dictionary extraction - NEW)
│   └── barcode-utils.js               (Barcode/QR helpers - NEW)
├── assets/
│   ├── logos/
│   │   ├── flash-express.svg          (Flash logo - create or source)
│   │   └── shopee-spx.svg             (Shopee logo - create or source)
│   └── fonts/                          (Optional custom fonts)
└── data/
    ├── metro-manila-addresses.json     (Expanded address data - NEW)
    ├── barangays.json                  (Barangay database - NEW)
    └── streets.json                    (Street name database - NEW)
```

---

## 🔧 IMPLEMENTATION PHASES

### PHASE 1: Core Architecture (Priority 1)

**Files to Create:**

1. **`core/courier-registry.js`**
   - Implement `CourierRegistry` class
   - Methods: `registerCourier()`, `getCourier()`, `getAllCouriers()`, `hasCourier()`, `validateCourierConfig()`
   - Use a `Map` for courier storage
   - Validation: Check for required fields in `CourierConfig`

2. **`core/label-engine.js`**
   - Implement `LabelEngine` class
   - Methods: `setActiveCourier()`, `generateSingleLabel()`, `generateBatch()`, `getActiveCourier()`, `validateLabel()`
   - Store generated labels in an array for history
   - Use `crypto.randomUUID()` or timestamp-based IDs for label IDs

3. **`core/label-renderer.js`**
   - Implement `LabelRenderer` class
   - Methods: `renderLabel()`, `renderBatch()`, `captureAsImage()`, `downloadAsImage()`, `downloadAsPDF()`, `clearAll()`, `removeLabel()`
   - Use `html2canvas` for image capture
   - Use `JsBarcode` for barcode rendering
   - Use `qrcodejs` for QR code rendering

4. **`core/ground-truth-exporter.js`**
   - Implement `GroundTruthExporter` class
   - Methods: `generateGroundTruth()`, `exportAsJSON()`, `bundleAndDownload()`, `generateManifest()`
   - Use `JSZip` for ZIP creation
   - Generate manifest with batch statistics

**Acceptance Criteria:**

- All core classes instantiate without errors
- Methods throw appropriate errors for invalid inputs
- Unit tests pass (manual testing acceptable)
- JSDoc comments complete

---

### PHASE 2: Flash Express Refactor (Priority 1)

**Objective:** Migrate existing Flash Express code into the modular architecture without breaking functionality.

**Files to Create/Modify:**

1. **`couriers/flash-express.js`**
   - Extract existing RTS sort code logic from `app.js`
   - Create `FLASH_EXPRESS_CONFIG` object matching `CourierConfig` interface
   - Implement template function that generates the current Flash Express HTML
   - Migrate barangay/district data from `app.js`

2. **`utils/data-generators.js`**
   - Move generic functions: `getRandomBuyerName()`, `getRandomWeight()`, `getRandomQuantity()`
   - Keep Flash-specific generators in `flash-express.js`

3. **`utils/barcode-utils.js`**
   - Create wrapper functions for `JsBarcode` and `QRCode`
   - Function signatures:
     ```javascript
     function generateBarcode(elementId, value, options = {})
     function generateQRCode(elementId, value, options = {})
     ```

**Migration Checklist:**

- [ ] All existing Flash Express features work
- [ ] RTS codes generate correctly
- [ ] Barangay/district selector still functional
- [ ] QR codes and barcodes render properly
- [ ] PDF download works
- [ ] Visual appearance unchanged

**Testing:**

- Generate 10 Flash Express labels
- Verify against existing output
- Check for console errors

---

### PHASE 3: Shopee SPX Implementation (Priority 2)

**Objective:** Implement complete Shopee SPX support with accurate template and data generation.

**Files to Create:**

1. **`couriers/shopee-spx.js`**
   - Create `SHOPEE_SPX_CONFIG` object
   - Implement all data generators:
     - `trackingNumber()`: `SPX` + 9 digits
     - `orderId()`: `SH` + 10 alphanumeric
     - `sortCode()`: `[HUB]-[AREA]-[SUB]-[SEQ]` format
     - `routeCode()`: `[HUB]-[LETTER]` format (e.g., `PAT-C`)
     - `codAmount()`: 70% COD, ₱100-₱5000
   - Implement template function with Shopee SPX HTML structure
   - Add expanded Metro Manila address dictionaries

2. **`styles.css`** (additions)
   - Add `.shopee-spx-label` styles
   - Implement Shopee SPX layout (header, sections, footer)
   - Use Shopee orange (#ee4d2d) as primary color
   - Ensure tagline "Ang Dali-Dali sa Shopee with On-Time Delivery Guarantee" is prominent

**Shopee SPX Template Requirements:**

- **Header:** Shopee SPX logo + Delivery Sort Code
- **Order Section:** Order ID/SN with barcode (Code 128)
- **Tracking Section:** Tracking number with barcode + Route code
- **Buyer Address:** Name + full address (NO PHONE NUMBERS)
- **Seller Address:** Name + full address
- **Product Details:** Description, Weight, Quantity, COD amount (highlighted if COD)
- **QR Code:** Optional but recommended
- **Footer:** Tagline in Shopee orange background

**Testing:**

- Generate 10 Shopee SPX labels
- Compare visual layout with spec PDF (if available) or real Shopee receipts
- Verify all fields populate correctly
- Check COD highlighting works

---

### PHASE 4: Ground Truth Export (Priority 2)

**Objective:** Implement JSON ground truth export and ZIP bundling.

**Implementation in `core/ground-truth-exporter.js`:**

1. **`generateGroundTruth(labelData, options)`**
   - Create JSON structure matching contract specification
   - Include all text fields with exact values
   - Add metadata (timestamp, generator version, image filename)
   - Optionally include bounding box placeholders (for future OCR)

2. **`bundleAndDownload(labelDataArray, options)`**
   - For each label:
     - Capture image using `labelRenderer.captureAsImage()`
     - Generate ground truth JSON
     - Add both to ZIP using JSZip
   - Generate `manifest.json` with batch statistics
   - Trigger browser download of ZIP file

**Ground Truth JSON Structure:**

```json
{
    "labelId": "label-FE034521A3F7G2-20250215-143022",
    "courierId": "flash-express",
    "imageFilename": "label-FE034521A3F7G2.png",
    "generatedAt": "2025-02-15T14:30:22.456Z",
    "generatorVersion": "1.0.0",
    "fields": {
        "trackingNumber": { "value": "FE3457892341" },
        "orderId": { "value": "FE034521A3F7G2" },
        "sortCode": { "value": "FEX-BUL-SJDM-MZN1-GY01" },
        "buyerName": { "value": "John Smith" },
        "buyerStreet": { "value": "123 Mabini St" },
        "buyerBarangay": { "value": "Muzon" },
        "buyerDistrict": { "value": "North" },
        "buyerCity": { "value": "San Jose del Monte" },
        "buyerProvince": { "value": "Bulacan" },
        "buyerZipCode": { "value": "3023" },
        "sellerName": { "value": "Flash Express" },
        "sellerAddress": { "value": "Gaya-Gaya Warehouse, SJDM, Bulacan 3023" },
        "weight": { "value": "1500g" },
        "quantity": { "value": "3" }
    },
    "metadata": {
        "labelDimensions": { "width": 400, "height": 600 },
        "imageScale": 3
    }
}
```

**Testing:**

- Generate batch of 10 labels
- Download as ZIP
- Extract and verify:
  - 10 PNG images
  - 10 JSON files
  - 1 manifest.json
  - All filenames match
  - JSON data matches label content

---

### PHASE 5: UI Enhancement (Priority 2)

**Objective:** Redesign the UI with a clean white enterprise look and parcel theme.

**Key UI Changes in `index.html`:**

1. **Hero Section**
   - Large parcel icon (📦) with floating animation
   - Title: "Multi-Courier Parcel Generator"
   - Tagline: "Generate realistic shipping labels for OCR training"

2. **Courier Selector**
   - Tabbed interface with courier logos
   - Active tab highlighted
   - Smooth transitions

3. **Generation Controls**
   - Button groups with clear hierarchy
   - Primary action: "Generate Single"
   - Secondary: "Generate Batch (5)", "Custom Batch..."
   - Success: "Download All (PNG + JSON)"
   - Danger: "Clear All"

4. **Stats Bar**
   - Display total generated, per-courier counts
   - Update in real-time

5. **Label Grid**
   - Masonry layout (CSS Grid)
   - Hover effects (lift on hover)
   - Action buttons overlay (download, remove)

6. **Toast Notifications**
   - Success: "Label generated successfully!"
   - Error: "Failed to generate label: [reason]"
   - Position: Top-right corner
   - Auto-dismiss after 3 seconds

7. **Loading Overlay**
   - Semi-transparent black overlay
   - Spinner animation
   - Text: "Generating labels..."

**CSS Styling (`styles.css`):**

- Use CSS variables for colors (see contract Section 7.2)
- White background (#ffffff) for main container
- Subtle box-shadow for depth
- Parcel tape effect on corners (optional decorative element)
- Responsive design (grid collapses to 1 column on mobile)

**Testing:**

- Test on desktop (1920x1080)
- Test on tablet (1024x768)
- Test on mobile (375x667)
- Verify all interactions work
- Check for visual bugs

---

### PHASE 6: Dictionary Extraction (Priority 3)

**Objective:** Implement utility to extract unique field values for OCR backend.

**Implementation in `utils/dictionary-extractor.js`:**

```javascript
/**
 * Extract all unique values for specified fields from label data
 * @param {LabelData[]} labelDataArray - Array of label data
 * @param {string[]} fieldNames - Fields to extract
 * @returns {Object.<string, string[]>} Dictionary object
 */
function extractDictionaries(labelDataArray, fieldNames) {
    const dictionaries = {};
    
    for (const fieldName of fieldNames) {
        const uniqueValues = new Set();
        
        for (const labelData of labelDataArray) {
            // Navigate nested fields (e.g., 'buyerAddress.barangay')
            const value = getNestedValue(labelData, fieldName);
            if (value) {
                uniqueValues.add(value);
            }
        }
        
        dictionaries[fieldName] = Array.from(uniqueValues).sort();
    }
    
    return dictionaries;
}

/**
 * Export dictionaries as JSON file
 */
async function exportDictionariesAsJSON(dictionaries, filename = 'dictionaries.json') {
    const blob = new Blob([JSON.stringify(dictionaries, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

/**
 * Generate Python dict literal (for easy copy-paste into Python backend)
 */
function generatePythonDict(dictionaries) {
    let pythonDict = '{\n';
    for (const [key, values] of Object.entries(dictionaries)) {
        pythonDict += `    "${key}": [\n`;
        for (const value of values) {
            pythonDict += `        "${value}",\n`;
        }
        pythonDict += `    ],\n`;
    }
    pythonDict += '}';
    return pythonDict;
}
```

**Usage Example:**

```javascript
// After generating 1000 labels
const allLabels = labelEngine.getGeneratedLabels();

const dictionaries = DictionaryExtractor.extractDictionaries(allLabels, [
    'buyerAddress.barangay',
    'buyerAddress.district',
    'sortCode',
    'riderCode'
]);

await DictionaryExtractor.exportDictionariesAsJSON(dictionaries);
```

**Testing:**

- Generate 100 labels (mixed couriers)
- Extract dictionaries
- Verify output contains unique values only
- Check JSON file is valid
- Test Python dict generation

---

### PHASE 7: Testing & Polish (Priority 3)

**Testing Checklist:**

- [ ] **Visual Fidelity Tests**
  - Flash Express labels match existing design
  - Shopee SPX labels match spec/real receipts
  - Fonts, colors, sizes accurate

- [ ] **Functional Tests**
  - Single label generation works
  - Batch generation works (5, 10, 100)
  - Courier switching works
  - Location selectors work
  - Download as PNG works
  - Download as PDF works
  - Download all as ZIP works
  - Clear all works

- [ ] **Ground Truth Validation**
  - JSON structure matches contract
  - All fields present in JSON
  - Values match label exactly
  - No typos or OCR errors in ground truth

- [ ] **Performance Tests**
  - Single label: < 500ms
  - 10 labels: < 5 seconds
  - 100 labels: < 60 seconds
  - Image capture: < 2 seconds per label

- [ ] **Browser Compatibility**
  - Chrome 90+: ✅
  - Firefox 88+: ✅
  - Safari 14+: ✅

- [ ] **Responsive Design**
  - Desktop: ✅
  - Tablet: ✅
  - Mobile: ✅

**Bug Fixes & Polish:**

- Remove all `console.log` statements
- Fix any visual bugs
- Optimize image capture performance
- Add error handling for edge cases
- Improve loading indicators

---

## 📚 DATA FILES TO CREATE

### 1. `data/metro-manila-addresses.json`

Expand the existing barangay data to include more Metro Manila areas:

```json
{
    "cities": [
        {
            "name": "San Jose del Monte",
            "province": "Bulacan",
            "zipCodes": ["3023", "3024"],
            "barangays": [
                {
                    "name": "Muzon",
                    "districts": ["North", "South", "Central", "Proper"],
                    "streets": ["Mabini St", "Rizal Ave", "Bonifacio St", "Kalayaan Ave"]
                },
                {
                    "name": "Tungko",
                    "districts": ["Main", "Subdivision"],
                    "streets": ["Main Street", "Del Pilar St", "Maginhawa St"]
                }
                // Add all existing barangays from current app.js
            ]
        },
        {
            "name": "Quezon City",
            "province": "Metro Manila",
            "zipCodes": ["1100", "1101", "1102", "1103", "1104"],
            "barangays": [
                {
                    "name": "Cubao",
                    "districts": ["Araneta Center", "Gateway", "Aurora"],
                    "streets": ["Aurora Blvd", "EDSA", "General Romulo Ave"]
                },
                {
                    "name": "Bagong Silang",
                    "districts": ["Phase 1", "Phase 2", "Phase 3"],
                    "streets": ["Commonwealth Ave", "Mindanao Ave"]
                }
                // Add more QC barangays
            ]
        },
        {
            "name": "Makati",
            "province": "Metro Manila",
            "zipCodes": ["1200", "1201", "1202"],
            "barangays": [
                {
                    "name": "Poblacion",
                    "districts": ["Barangay 1", "Barangay 2"],
                    "streets": ["Kalayaan Ave", "P. Burgos St", "Arnaiz Ave"]
                },
                {
                    "name": "Salcedo",
                    "districts": ["Village", "Commercial"],
                    "streets": ["Ayala Ave", "Paseo de Roxas", "Buendia Ave"]
                }
            ]
        }
        // Add more cities: Manila, Pasig, Taguig, Paranaque, etc.
    ]
}
```

**Minimum Requirements:**

- At least 10 cities
- At least 50 total barangays
- At least 100 unique streets
- Realistic zip codes

### 2. `data/barangays.json`

Simplified flat list for quick lookups:

```json
[
    "Muzon",
    "Tungko",
    "Sapang Palay",
    "Gaya-Gaya",
    "Graceville",
    "Cubao",
    "Bagong Silang",
    "Poblacion",
    "Salcedo",
    // ... more barangays
]
```

### 3. `data/streets.json`

Large pool of Philippine street names:

```json
[
    "Mabini St",
    "Rizal Ave",
    "Bonifacio St",
    "Aurora Blvd",
    "EDSA",
    "Commonwealth Ave",
    "Ayala Ave",
    "Ortigas Ave",
    "C5 Road",
    "Quezon Ave",
    "Shaw Blvd",
    "Buendia Ave",
    "Taft Ave",
    "España Blvd",
    // ... at least 100 unique streets
]
```

---

## 🎨 LOGO ASSETS

### Flash Express Logo (`assets/logos/flash-express.svg`)

**Options:**

1. **Create from scratch:** Simple SVG with "FLASH" text and lightning bolt icon
2. **Source from official:** If publicly available (check brand guidelines)
3. **Placeholder:** Use a colored rectangle with text until final logo is available

**Specifications:**

- Format: SVG (scalable)
- Size: 120x40px (aspect ratio maintained)
- Colors: #ff6b35 (primary), white (text)

### Shopee SPX Logo (`assets/logos/shopee-spx.svg`)

**Specifications:**

- Format: SVG
- Size: 120x40px
- Colors: #ee4d2d (Shopee orange)
- Must include "SPX" text prominently

**Note:** If official logos cannot be obtained, use text-based placeholders with correct brand colors.

---

## 🚨 CRITICAL GOTCHAS & PITFALLS

### 1. HTML2Canvas Performance

**Problem:** `html2canvas` can be slow on complex DOM elements.

**Solution:**

- Hide labels that are not being captured
- Use `scale: 3` for quality but be aware it increases processing time
- Consider progressive rendering (capture in batches, show progress)

### 2. JSZip Memory Limits

**Problem:** Large ZIP files (>500MB) may cause memory issues.

**Solution:**

- Limit batch size to 100 labels max
- Compress images if possible (use JPEG at 85% quality instead of PNG)
- Show warning if estimated ZIP size exceeds 400MB

### 3. Barcode Generation Failures

**Problem:** Invalid barcode values cause `JsBarcode` to fail silently.

**Solution:**

- Always validate barcode values before generation
- Use try-catch around `JsBarcode()` calls
- Fall back to text if barcode fails

### 4. QR Code Overwriting

**Problem:** If QR code container has existing QR, `new QRCode()` will append instead of replace.

**Solution:**

- Always clear container before generating: `container.innerHTML = ''`
- Or use unique IDs per label

### 5. Async Race Conditions

**Problem:** Batch operations may complete out of order.

**Solution:**

- Use `Promise.all()` for concurrent operations
- Use `await` for sequential operations that must complete in order
- Show progress indicators

### 6. Ground Truth Accuracy

**Problem:** Ground truth data doesn't match rendered label.

**Solution:**

- Use the same data object for both rendering and ground truth
- Never copy-paste values manually
- Automated test: Compare rendered text with JSON values

---

## ✅ SUCCESS CRITERIA

**Phase Complete When:**

- All files created and structured correctly
- All classes implement contract interfaces
- Both couriers (Flash Express, Shopee SPX) work perfectly
- Ground truth export produces valid JSON and ZIP
- Dictionary extraction works
- UI is polished and responsive
- Performance benchmarks met
- All tests pass
- No console errors

**Deliverables:**

1. Complete `parcel_generator/` directory with all files
2. Working demo (can be tested in browser)
3. Sample batch export (ZIP with 10 labels + JSON)
4. Sample dictionary extraction output
5. Brief README.md with setup/usage instructions

---

## 📞 QUESTIONS FOR CLARIFICATION

Before starting implementation, clarify:

1. Do you have official courier logos (Flash Express, Shopee SPX)?
2. Do you have sample Shopee SPX receipts for visual reference?
3. What is the priority: accuracy vs. speed of implementation?
4. Should we support IE11 or only modern browsers?
5. Do you need authentication/user accounts or is this a standalone tool?

---

## 🔄 NEXT STEPS AFTER IMPLEMENTATION

Once implementation is complete:

1. **Code Review** - Submit for review by Auditor agent
2. **Integration Testing** - Test with OCR backend (if available)
3. **User Acceptance Testing** - Get feedback from end users
4. **Documentation** - Complete README, API docs, user guide
5. **Deployment** - Host on GitHub Pages or similar platform

---

**Ready to Start?** Begin with Phase 1 (Core Architecture) and work sequentially through the phases. Good luck! 🚀

---

**Work Order Version:** 1.0
**Created:** 2025-02-15
**Contract Reference:** CONTRACT_MULTI_COURIER_GENERATOR.md v1.0