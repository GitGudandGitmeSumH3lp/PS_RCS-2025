# CONTRACT: Multi-Courier Parcel Generator System
**Version:** 1.0
**Last Updated:** 2025-02-15
**Status:** Draft

## 1. PURPOSE

This system extends the existing Flash Express shipping label generator to support multiple courier services (Flash Express, Shopee SPX, and future couriers) with a modular, template-based architecture. The system generates realistic shipping labels with accurate ground truth data for OCR training, supports batch generation, and provides dictionary extraction utilities for backend integration.

## 2. SYSTEM ARCHITECTURE

### 2.1 Directory Structure

```
parcel_generator/
├── index.html                          # Main UI (enhanced with parcel theme)
├── styles.css                          # Global styles (white enterprise + parcel theme)
├── app.js                              # Main application controller
├── couriers/
│   ├── flash-express.js               # Flash Express configuration & generators
│   ├── shopee-spx.js                  # Shopee SPX configuration & generators
│   └── courier-template.js            # Template for adding new couriers
├── core/
│   ├── label-engine.js                # Core label generation logic
│   ├── label-renderer.js              # DOM rendering & image capture
│   ├── courier-registry.js            # Courier management system
│   └── ground-truth-exporter.js       # JSON export & ZIP bundling
├── utils/
│   ├── data-generators.js             # Shared data generation utilities
│   ├── dictionary-extractor.js        # Dictionary extraction for Phase 7.7
│   └── barcode-utils.js               # Barcode/QR code generation helpers
├── assets/
│   ├── logos/
│   │   ├── flash-express.svg          # Flash Express logo
│   │   └── shopee-spx.svg             # Shopee SPX logo
│   └── fonts/                          # Custom fonts if needed
└── data/
    ├── metro-manila-addresses.json     # Expanded address dictionaries
    ├── barangays.json                  # Barangay database
    └── streets.json                    # Street name database
```

### 2.2 Technology Stack

- **Frontend:** Vanilla JavaScript (ES6+), HTML5, CSS3
- **Libraries:**
  - `html2canvas` (v1.4.1) - Label to image conversion
  - `JsBarcode` (v3.11.5) - Barcode generation (Code 128)
  - `qrcodejs` (v1.0.0) - QR code generation
  - `JSZip` (v3.10.1) - Batch download packaging
  - `jsPDF` (v2.5.1) - PDF export (optional)

---

## 3. CORE INTERFACES

### 3.1 CourierConfig Interface

**Purpose:** Define the complete configuration for a courier service, including branding, data generators, templates, and validation rules.

```javascript
/**
 * @typedef {Object} CourierConfig
 * @property {string} id - Unique courier identifier (e.g., 'flash-express', 'shopee-spx')
 * @property {string} name - Display name (e.g., 'Flash Express', 'Shopee SPX')
 * @property {BrandingConfig} branding - Visual branding configuration
 * @property {DataGenerators} generators - Data generation functions
 * @property {LayoutConfig} layout - HTML template and CSS configuration
 * @property {DataDictionaries} dataDictionaries - Address and field dictionaries
 * @property {ValidationRules} validation - Field validation rules
 */

/**
 * @typedef {Object} BrandingConfig
 * @property {string} primaryColor - Primary brand color (hex)
 * @property {string} secondaryColor - Secondary brand color (hex)
 * @property {string} logoPath - Path to courier logo SVG
 * @property {string} tagline - Courier tagline text
 * @property {string} fontFamily - Primary font family
 */

/**
 * @typedef {Object} DataGenerators
 * @property {Function} trackingNumber - () => string
 * @property {Function} orderId - () => string
 * @property {Function} sortCode - (barangay: string, district: string) => string
 * @property {Function} routeCode - (barangay: string) => string
 * @property {Function} hubCode - () => string
 * @property {Function} deliveryCode - (district: string) => string
 * @property {Function} phNumber - () => string (for barcodes)
 * @property {Function} weight - () => number
 * @property {Function} quantity - (weight: number) => number
 */

/**
 * @typedef {Object} LayoutConfig
 * @property {Function} templateFunction - (data: LabelData) => string (HTML)
 * @property {string} cssClassName - Root CSS class for courier-specific styling
 * @property {Object} dimensions - { width: number, height: number } (in pixels)
 * @property {string[]} requiredFields - Array of field names that must be present
 */

/**
 * @typedef {Object} DataDictionaries
 * @property {string[]} barangays - Available barangays for this courier
 * @property {Object.<string, string[]>} districts - Barangay -> district mappings
 * @property {string[]} streets - Street name pool
 * @property {string[]} cities - City name pool
 * @property {string[]} provinces - Province name pool
 */

/**
 * @typedef {Object} ValidationRules
 * @property {number} maxWeight - Maximum weight in grams
 * @property {RegExp} trackingNumberPattern - Validation regex
 * @property {RegExp} orderIdPattern - Validation regex
 * @property {string[]} requiredAddressFields - Array of required address components
 */
```

### 3.2 LabelEngine Class

**Purpose:** Orchestrate label generation, manage courier switching, and coordinate batch operations.

```javascript
/**
 * @class LabelEngine
 * @description Core engine for managing label generation across multiple couriers
 */
class LabelEngine {
    /**
     * @constructor
     * @param {CourierRegistry} courierRegistry - Registry of available couriers
     */
    constructor(courierRegistry) {}

    /**
     * Set the active courier for subsequent label generation
     * @param {string} courierId - Courier identifier
     * @throws {Error} If courier ID is not registered
     * @returns {void}
     */
    setActiveCourier(courierId) {}

    /**
     * Generate a single label with the active courier
     * @param {Object} [overrides] - Optional field overrides
     * @param {string} [overrides.barangay] - Specific barangay selection
     * @param {string} [overrides.district] - Specific district selection
     * @param {string} [overrides.buyerName] - Custom buyer name
     * @returns {LabelData} Generated label data with ground truth
     */
    generateSingleLabel(overrides = {}) {}

    /**
     * Generate multiple labels in batch
     * @param {number} count - Number of labels to generate
     * @param {Object} [options] - Batch generation options
     * @param {boolean} [options.randomCourier=false] - Use random courier per label
     * @param {string[]} [options.courierPool] - Specific couriers to use (if randomCourier=true)
     * @param {Object} [options.overrides] - Common overrides for all labels
     * @returns {LabelData[]} Array of generated label data
     */
    generateBatch(count, options = {}) {}

    /**
     * Get the current active courier configuration
     * @returns {CourierConfig} Active courier configuration
     */
    getActiveCourier() {}

    /**
     * Validate label data against courier rules
     * @param {LabelData} labelData - Label data to validate
     * @returns {ValidationResult} Validation result with errors if any
     */
    validateLabel(labelData) {}
}

/**
 * @typedef {Object} LabelData
 * @property {string} courierId - Courier identifier
 * @property {string} trackingNumber - Unique tracking number
 * @property {string} orderId - Order/parcel ID
 * @property {string} sortCode - Delivery sort code
 * @property {string} routeCode - Route code (if applicable)
 * @property {string} hubCode - Hub identifier
 * @property {AddressData} buyerAddress - Buyer address details
 * @property {AddressData} sellerAddress - Seller address details
 * @property {string} buyerName - Buyer full name
 * @property {string} sellerName - Seller full name
 * @property {number} weight - Parcel weight in grams
 * @property {number} quantity - Number of items
 * @property {number} codAmount - COD amount (0 if non-COD)
 * @property {string} phNumber - Barcode number
 * @property {Object} metadata - Additional metadata
 * @property {Date} metadata.generatedAt - Generation timestamp
 * @property {string} metadata.generatorVersion - System version
 */

/**
 * @typedef {Object} AddressData
 * @property {string} street - Street address with number
 * @property {string} barangay - Barangay name
 * @property {string} district - District/subdivision name
 * @property {string} city - City name
 * @property {string} province - Province name
 * @property {string} zipCode - Postal code
 * @property {string} full - Complete formatted address
 * @property {string} code - Area/district code (for sorting)
 */

/**
 * @typedef {Object} ValidationResult
 * @property {boolean} valid - Whether validation passed
 * @property {string[]} errors - Array of error messages (empty if valid)
 * @property {string[]} warnings - Array of warning messages
 */
```

### 3.3 LabelRenderer Class

**Purpose:** Handle DOM rendering, image capture, and visual export operations.

```javascript
/**
 * @class LabelRenderer
 * @description Manages label rendering to DOM and image/PDF export
 */
class LabelRenderer {
    /**
     * @constructor
     * @param {HTMLElement} containerElement - Target DOM container for labels
     */
    constructor(containerElement) {}

    /**
     * Render a label to the DOM
     * @param {LabelData} labelData - Label data to render
     * @param {CourierConfig} courierConfig - Courier configuration for template
     * @returns {Promise<string>} Promise resolving to label DOM element ID
     */
    async renderLabel(labelData, courierConfig) {}

    /**
     * Render multiple labels in batch
     * @param {LabelData[]} labelDataArray - Array of label data
     * @param {CourierRegistry} courierRegistry - Registry for courier configs
     * @returns {Promise<string[]>} Promise resolving to array of label element IDs
     */
    async renderBatch(labelDataArray, courierRegistry) {}

    /**
     * Capture label as image
     * @param {string} labelElementId - DOM element ID of label
     * @param {Object} [options] - Capture options
     * @param {number} [options.scale=3] - Rendering scale for quality
     * @param {string} [options.format='png'] - Image format ('png', 'jpg')
     * @returns {Promise<Blob>} Promise resolving to image blob
     */
    async captureAsImage(labelElementId, options = {}) {}

    /**
     * Download label as image file
     * @param {string} labelElementId - DOM element ID of label
     * @param {string} [filename] - Custom filename (auto-generated if omitted)
     * @param {string} [format='png'] - Image format
     * @returns {Promise<void>}
     */
    async downloadAsImage(labelElementId, filename = null, format = 'png') {}

    /**
     * Download label as PDF
     * @param {string} labelElementId - DOM element ID of label
     * @param {string} [filename] - Custom filename
     * @returns {Promise<void>}
     */
    async downloadAsPDF(labelElementId, filename = null) {}

    /**
     * Clear all rendered labels from DOM
     * @returns {void}
     */
    clearAll() {}

    /**
     * Remove a specific label from DOM
     * @param {string} labelElementId - DOM element ID of label to remove
     * @returns {void}
     */
    removeLabel(labelElementId) {}
}
```

### 3.4 CourierRegistry Class

**Purpose:** Centralized management of available couriers with registration and lookup.

```javascript
/**
 * @class CourierRegistry
 * @description Manages available courier configurations
 */
class CourierRegistry {
    /**
     * @constructor
     */
    constructor() {}

    /**
     * Register a new courier configuration
     * @param {CourierConfig} courierConfig - Courier configuration object
     * @throws {Error} If courier ID already exists or config is invalid
     * @returns {void}
     */
    registerCourier(courierConfig) {}

    /**
     * Get courier configuration by ID
     * @param {string} courierId - Courier identifier
     * @throws {Error} If courier ID not found
     * @returns {CourierConfig} Courier configuration
     */
    getCourier(courierId) {}

    /**
     * Get all registered courier IDs
     * @returns {string[]} Array of courier IDs
     */
    getAllCourierIds() {}

    /**
     * Get all registered courier configurations
     * @returns {CourierConfig[]} Array of courier configs
     */
    getAllCouriers() {}

    /**
     * Check if courier is registered
     * @param {string} courierId - Courier identifier
     * @returns {boolean} True if registered
     */
    hasCourier(courierId) {}

    /**
     * Unregister a courier
     * @param {string} courierId - Courier identifier
     * @returns {boolean} True if unregistered, false if not found
     */
    unregisterCourier(courierId) {}

    /**
     * Validate courier configuration structure
     * @param {CourierConfig} courierConfig - Config to validate
     * @returns {ValidationResult} Validation result
     */
    validateCourierConfig(courierConfig) {}
}
```

### 3.5 GroundTruthExporter Class

**Purpose:** Export ground truth data as JSON and bundle with images into ZIP archives.

```javascript
/**
 * @class GroundTruthExporter
 * @description Handles ground truth JSON generation and batch ZIP export
 */
class GroundTruthExporter {
    /**
     * @constructor
     * @param {LabelRenderer} labelRenderer - Label renderer instance
     */
    constructor(labelRenderer) {}

    /**
     * Generate ground truth JSON for a single label
     * @param {LabelData} labelData - Label data
     * @param {Object} [options] - Export options
     * @param {boolean} [options.includeMetadata=true] - Include generation metadata
     * @returns {GroundTruthData} Ground truth JSON structure
     */
    generateGroundTruth(labelData, options = {}) {}

    /**
     * Export ground truth as JSON file
     * @param {GroundTruthData} groundTruth - Ground truth data
     * @param {string} [filename] - Custom filename
     * @returns {Promise<void>}
     */
    async exportAsJSON(groundTruth, filename = null) {}

    /**
     * Bundle multiple labels with ground truth into ZIP
     * @param {LabelData[]} labelDataArray - Array of label data
     * @param {Object} [options] - Bundle options
     * @param {string} [options.imageFormat='png'] - Image format for labels
     * @param {boolean} [options.includeManifest=true] - Include manifest.json
     * @param {string} [options.zipFilename] - Custom ZIP filename
     * @returns {Promise<void>} Promise resolving when download starts
     */
    async bundleAndDownload(labelDataArray, options = {}) {}

    /**
     * Generate a batch manifest file
     * @param {LabelData[]} labelDataArray - Array of label data
     * @returns {BatchManifest} Manifest data structure
     */
    generateManifest(labelDataArray) {}
}

/**
 * @typedef {Object} GroundTruthData
 * @property {string} labelId - Unique label identifier
 * @property {string} courierId - Courier identifier
 * @property {Object} fields - All text fields with exact values
 * @property {string} fields.trackingNumber
 * @property {string} fields.orderId
 * @property {string} fields.sortCode
 * @property {string} fields.buyerName
 * @property {string} fields.buyerStreet
 * @property {string} fields.buyerBarangay
 * @property {string} fields.buyerDistrict
 * @property {string} fields.buyerCity
 * @property {string} fields.buyerProvince
 * @property {string} fields.buyerZipCode
 * @property {string} fields.sellerName
 * @property {string} fields.sellerAddress
 * @property {string} fields.weight
 * @property {string} fields.quantity
 * @property {string} fields.codAmount (if applicable)
 * @property {Object} metadata
 * @property {string} metadata.imageFilename - Associated image filename
 * @property {Date} metadata.generatedAt
 * @property {string} metadata.generatorVersion
 * @property {Object} metadata.boundingBoxes - Optional OCR bounding box hints
 */

/**
 * @typedef {Object} BatchManifest
 * @property {string} batchId - Unique batch identifier
 * @property {Date} generatedAt - Batch generation timestamp
 * @property {number} totalLabels - Total number of labels
 * @property {Object.<string, number>} courierCounts - Label count per courier
 * @property {string[]} labelIds - Array of label IDs in batch
 * @property {string} generatorVersion - System version
 */
```

### 3.6 DictionaryExtractor Utility

**Purpose:** Extract unique field values from generated labels for OCR backend dictionary creation.

```javascript
/**
 * @namespace DictionaryExtractor
 * @description Utility functions for extracting dictionaries from generated labels
 */

/**
 * Extract all unique values for specified fields
 * @param {LabelData[]} labelDataArray - Array of label data
 * @param {string[]} fieldNames - Fields to extract (e.g., ['barangay', 'district', 'riderCode'])
 * @returns {ExtractedDictionaries} Dictionary object with field -> unique values
 */
function extractDictionaries(labelDataArray, fieldNames) {}

/**
 * Export dictionaries as JSON file
 * @param {ExtractedDictionaries} dictionaries - Extracted dictionaries
 * @param {string} [filename='dictionaries.json'] - Output filename
 * @returns {Promise<void>}
 */
async function exportDictionariesAsJSON(dictionaries, filename = 'dictionaries.json') {}

/**
 * Generate Python-compatible dictionary format
 * @param {ExtractedDictionaries} dictionaries - Extracted dictionaries
 * @returns {string} Python dict literal as string
 */
function generatePythonDict(dictionaries) {}

/**
 * @typedef {Object.<string, string[]>} ExtractedDictionaries
 * @description Object mapping field names to arrays of unique values
 * @example
 * {
 *   barangay: ['Muzon', 'Tungko', 'Sapang Palay'],
 *   district: ['North', 'South', 'Central', 'West', 'East'],
 *   riderCode: ['GY01', 'GY02', 'GY03']
 * }
 */
```

---

## 4. COURIER-SPECIFIC IMPLEMENTATIONS

### 4.1 Flash Express Configuration

**File:** `couriers/flash-express.js`

```javascript
/**
 * Flash Express courier configuration
 * Based on existing implementation in current app.js
 */

const FLASH_EXPRESS_CONFIG = {
    id: 'flash-express',
    name: 'Flash Express',
    branding: {
        primaryColor: '#ff6b35',
        secondaryColor: '#e55a2b',
        logoPath: 'assets/logos/flash-express.svg',
        tagline: 'FASTEST DELIVERY IN THE PHILIPPINES',
        subtag: 'WITH ON-TIME DELIVERY GUARANTEE',
        fontFamily: 'Arial, sans-serif'
    },
    generators: {
        trackingNumber: () => {
            const prefix = 'FE';
            const middle = Math.floor(Math.random() * 9000000000 + 1000000000);
            return `${prefix}${middle}`;
        },
        orderId: () => {
            const timestamp = Date.now().toString().substr(-6);
            const random = Math.random().toString(36).substr(2, 6).toUpperCase();
            return `FE${timestamp}${random}`;
        },
        sortCode: (barangay, district) => {
            // Existing RTS code logic from app.js
            // Returns format: FEX-BUL-SJDM-[CODE]-[RIDER]
        },
        hubCode: () => {
            const codes = ['[GY]', '[HUB]', '[FEX]'];
            return codes[Math.floor(Math.random() * codes.length)];
        },
        phNumber: () => {
            return 'FE ' + Math.floor(Math.random() * 900000000000 + 100000000000);
        },
        weight: () => Math.floor(Math.random() * 7000) + 100,
        quantity: (weight) => Math.max(1, Math.floor(weight / 500))
    },
    layout: {
        templateFunction: (data) => {
            // Return HTML template string (existing label structure)
            // Should match current Flash Express label design
        },
        cssClassName: 'flash-express-label',
        dimensions: { width: 400, height: 600 }, // Approximate
        requiredFields: [
            'trackingNumber', 'orderId', 'sortCode', 'hubCode',
            'buyerName', 'buyerAddress', 'sellerName', 'sellerAddress',
            'weight', 'quantity', 'phNumber'
        ]
    },
    dataDictionaries: {
        barangays: [
            'Muzon', 'Graceville', 'Poblacion I', 'Loma de Gato',
            'Bagong Silang (Brgy 176)', 'Gaya-Gaya', 'Sapang Palay', 'Tungko'
        ],
        districts: {
            'Muzon': ['North', 'South', 'Central', 'Proper'],
            'Graceville': ['Subdivision', 'Main', 'Commercial'],
            // ... (existing district mappings)
        },
        streets: [
            'Mabini St', 'Rizal Ave', 'Bonifacio St', 'Mabuhay St',
            'Del Pilar St', 'Kalayaan Ave', 'Maginhawa St', 'Kamuning Rd',
            // ... (expanded list)
        ],
        cities: ['San Jose del Monte'],
        provinces: ['Bulacan']
    },
    validation: {
        maxWeight: 7000, // 7kg
        trackingNumberPattern: /^FE\d{10}$/,
        orderIdPattern: /^FE\d{6}[A-Z0-9]{6}$/,
        requiredAddressFields: ['street', 'barangay', 'district', 'city', 'province', 'zipCode']
    }
};
```

### 4.2 Shopee SPX Configuration

**File:** `couriers/shopee-spx.js`

**Based on Shopee SPX Air Waybill specifications:**

```javascript
/**
 * Shopee SPX courier configuration
 * Template based on Shopee SPX Air Waybill format
 */

const SHOPEE_SPX_CONFIG = {
    id: 'shopee-spx',
    name: 'Shopee SPX',
    branding: {
        primaryColor: '#ee4d2d', // Shopee orange
        secondaryColor: '#ff6b35',
        logoPath: 'assets/logos/shopee-spx.svg',
        tagline: 'Ang Dali-Dali sa Shopee with On-Time Delivery Guarantee',
        fontFamily: 'Arial, Helvetica, sans-serif'
    },
    generators: {
        trackingNumber: () => {
            const prefix = 'SPX';
            const digits = Math.floor(Math.random() * 900000000 + 100000000); // 9 digits
            return `${prefix}${digits}`;
        },
        orderId: () => {
            const prefix = 'SH';
            const alphanumeric = Array.from({ length: 10 }, () => 
                '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'[Math.floor(Math.random() * 36)]
            ).join('');
            return `${prefix}${alphanumeric}`;
        },
        sortCode: (barangay, district) => {
            // Format: [HUB]-[AREA]-[SUB]-[SEQ]
            // Example: 11-0902-3A-06
            const hub = Math.floor(Math.random() * 20) + 10; // 10-29
            const area = String(Math.floor(Math.random() * 1000)).padStart(4, '0');
            const sub = String.fromCharCode(65 + Math.floor(Math.random() * 26)) + 
                        String.fromCharCode(65 + Math.floor(Math.random() * 26));
            const seq = String(Math.floor(Math.random() * 100)).padStart(2, '0');
            return `${hub}-${area}-${sub}-${seq}`;
        },
        routeCode: (barangay) => {
            // Route codes like PAT-C, MNL-A, QC-B
            const hubs = ['PAT', 'MNL', 'QC', 'CLN', 'MKT'];
            const suffix = String.fromCharCode(65 + Math.floor(Math.random() * 26));
            return `${hubs[Math.floor(Math.random() * hubs.length)]}-${suffix}`;
        },
        deliveryCode: (district) => {
            // Simple delivery zone code
            return `D${Math.floor(Math.random() * 100) + 1}`;
        },
        phNumber: () => {
            // SPX barcode format
            return 'SPX' + Math.floor(Math.random() * 900000000000 + 100000000000);
        },
        weight: () => Math.floor(Math.random() * 5000) + 100, // Max 5kg
        quantity: (weight) => Math.max(1, Math.floor(weight / 400)),
        codAmount: () => {
            // 70% of parcels are COD
            if (Math.random() < 0.7) {
                return Math.floor(Math.random() * 5000) + 100; // ₱100-₱5100
            }
            return 0;
        }
    },
    layout: {
        templateFunction: (data) => {
            // HTML template for Shopee SPX label (see section 4.3)
        },
        cssClassName: 'shopee-spx-label',
        dimensions: { width: 400, height: 650 },
        requiredFields: [
            'trackingNumber', 'orderId', 'sortCode', 'routeCode',
            'buyerName', 'buyerAddress', 'sellerName', 'sellerAddress',
            'weight', 'quantity', 'codAmount'
        ]
    },
    dataDictionaries: {
        barangays: [
            // Expanded Metro Manila coverage
            'Muzon', 'Tungko', 'Sapang Palay', 'Gaya-Gaya',
            'Bagong Silang', 'Santa Cruz', 'Cubao', 'Makati',
            'Taguig', 'Paranaque', 'Pasay', 'Manila', 'Quezon City'
        ],
        districts: {
            'Muzon': ['North', 'South', 'Central'],
            'Tungko': ['Main', 'Subdivision'],
            'Bagong Silang': ['Phase 1', 'Phase 2', 'Phase 3'],
            'Cubao': ['Araneta Center', 'Gateway', 'Aurora'],
            'Makati': ['Poblacion', 'Salcedo', 'Legazpi'],
            // ... (expanded mappings)
        },
        streets: [
            'Aurora Blvd', 'EDSA', 'C5 Road', 'Ortigas Ave',
            'Ayala Ave', 'Buendia Ave', 'Taft Ave', 'España Blvd',
            'Commonwealth Ave', 'Quezon Ave', 'Shaw Blvd',
            // ... (Metro Manila streets)
        ],
        cities: [
            'San Jose del Monte', 'Manila', 'Quezon City', 'Makati',
            'Taguig', 'Pasig', 'Mandaluyong', 'Caloocan', 'Paranaque'
        ],
        provinces: ['Bulacan', 'Metro Manila']
    },
    validation: {
        maxWeight: 5000, // 5kg
        trackingNumberPattern: /^SPX\d{9}$/,
        orderIdPattern: /^SH[0-9A-Z]{10}$/,
        requiredAddressFields: ['street', 'barangay', 'city', 'province', 'zipCode']
    }
};
```

### 4.3 Shopee SPX HTML Template Structure

**Template Function Output (simplified):**

```html
<div class="shipping-label shopee-spx-label">
    <!-- HEADER SECTION -->
    <div class="spx-header">
        <img src="assets/logos/shopee-spx.svg" alt="Shopee SPX" class="spx-logo" />
        <div class="delivery-sort-code">
            <div class="label-small">Delivery Sort Code</div>
            <div class="sort-code-value">${data.sortCode}</div>
        </div>
    </div>

    <!-- ORDER INFO SECTION -->
    <div class="spx-order-section">
        <div class="order-row">
            <span class="label">Order ID/SN:</span>
            <span class="value">${data.orderId}</span>
        </div>
        <div class="barcode-container">
            <svg class="barcode" id="barcode-order-${data.orderId}"></svg>
        </div>
    </div>

    <!-- TRACKING NUMBER SECTION -->
    <div class="spx-tracking-section">
        <div class="tracking-row">
            <span class="label">Tracking Number:</span>
            <span class="value-large">${data.trackingNumber}</span>
        </div>
        <div class="barcode-container">
            <svg class="barcode" id="barcode-tracking-${data.orderId}"></svg>
        </div>
        <div class="route-code">Route: ${data.routeCode}</div>
    </div>

    <!-- BUYER ADDRESS -->
    <div class="spx-address-section buyer">
        <div class="section-header">BUYER / CONSIGNEE</div>
        <div class="address-content">
            <div class="name-large">${data.buyerName}</div>
            <div class="address-text">${data.buyerAddress.full}</div>
            <!-- NO PHONE NUMBERS as per spec -->
        </div>
    </div>

    <!-- SELLER ADDRESS -->
    <div class="spx-address-section seller">
        <div class="section-header">SELLER / SHIPPER</div>
        <div class="address-content">
            <div class="name-large">${data.sellerName}</div>
            <div class="address-text">${data.sellerAddress.full}</div>
        </div>
    </div>

    <!-- PRODUCT DETAILS -->
    <div class="spx-product-section">
        <div class="product-row">
            <span class="label">Product Description:</span>
            <span class="value">General Merchandise</span>
        </div>
        <div class="product-details">
            <div class="detail-item">
                <span class="label">Weight:</span>
                <span class="value">${data.weight}g</span>
            </div>
            <div class="detail-item">
                <span class="label">Quantity:</span>
                <span class="value">${data.quantity}</span>
            </div>
            ${data.codAmount > 0 ? `
            <div class="detail-item cod-highlight">
                <span class="label">COD Amount:</span>
                <span class="value">₱${data.codAmount.toFixed(2)}</span>
            </div>
            ` : ''}
        </div>
    </div>

    <!-- QR CODE (Optional) -->
    <div class="spx-qr-section">
        <div id="qr-${data.orderId}" class="qr-code"></div>
    </div>

    <!-- FOOTER WITH TAGLINE -->
    <div class="spx-footer">
        ${data.tagline}
    </div>
</div>
```

### 4.4 Shopee SPX CSS Styling (Additional)

**File:** `styles.css` (additions)

```css
/* Shopee SPX Specific Styles */
.shopee-spx-label {
    width: 400px;
    border: 3px solid #000;
    font-family: Arial, Helvetica, sans-serif;
    background: white;
}

.spx-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px;
    border-bottom: 2px solid #000;
    background: #fff8f0;
}

.spx-logo {
    height: 40px;
}

.delivery-sort-code {
    text-align: right;
}

.label-small {
    font-size: 9px;
    color: #666;
}

.sort-code-value {
    font-size: 20px;
    font-weight: bold;
    color: #ee4d2d;
}

.spx-order-section,
.spx-tracking-section {
    padding: 8px 10px;
    border-bottom: 1px solid #ccc;
}

.order-row,
.tracking-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 5px;
}

.value-large {
    font-size: 18px;
    font-weight: bold;
}

.route-code {
    font-size: 10px;
    color: #666;
    text-align: right;
    margin-top: 3px;
}

.spx-address-section {
    padding: 10px;
    border-bottom: 2px solid #000;
}

.section-header {
    background: #000;
    color: white;
    padding: 3px 6px;
    font-size: 10px;
    font-weight: bold;
    margin-bottom: 5px;
}

.name-large {
    font-size: 14px;
    font-weight: bold;
    margin-bottom: 3px;
}

.address-text {
    font-size: 11px;
    line-height: 1.4;
}

.spx-product-section {
    padding: 10px;
    border-bottom: 1px solid #ccc;
}

.product-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 11px;
}

.product-details {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    font-size: 10px;
}

.detail-item {
    display: flex;
    flex-direction: column;
}

.cod-highlight {
    background: #fff3cd;
    padding: 4px;
    border-radius: 3px;
}

.cod-highlight .value {
    color: #ee4d2d;
    font-weight: bold;
    font-size: 13px;
}

.spx-qr-section {
    padding: 10px;
    text-align: center;
    border-bottom: 2px solid #000;
}

.spx-qr-section .qr-code {
    width: 80px;
    height: 80px;
    margin: 0 auto;
}

.spx-footer {
    background: #ee4d2d;
    color: white;
    text-align: center;
    padding: 10px;
    font-size: 11px;
    font-weight: bold;
}
```

---

## 5. DATA GENERATION SPECIFICATIONS

### 5.1 Address Generation Enhancement

**Expanded Metro Manila Coverage:**

Create comprehensive address dictionaries in `data/metro-manila-addresses.json`:

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
                    "streets": ["Mabini St", "Rizal Ave", "Bonifacio St"]
                }
                // ... more barangays
            ]
        },
        {
            "name": "Quezon City",
            "province": "Metro Manila",
            "zipCodes": ["1100", "1101", "1102"],
            "barangays": [
                {
                    "name": "Cubao",
                    "districts": ["Araneta Center", "Gateway", "Aurora"],
                    "streets": ["Aurora Blvd", "EDSA", "General Romulo"]
                }
                // ... more barangays
            ]
        }
        // ... more cities
    ]
}
```

### 5.2 Realistic Data Generation Rules

**Tracking Number Patterns:**

- **Flash Express:** `FE` + 10 digits (e.g., `FE3457892341`)
- **Shopee SPX:** `SPX` + 9 digits (e.g., `SPX123456789`)

**Order ID Patterns:**

- **Flash Express:** `FE` + 6-digit timestamp + 6-char alphanumeric (e.g., `FE034521A3F7G2`)
- **Shopee SPX:** `SH` + 10-char alphanumeric (e.g., `SH1A2B3C4D5E`)

**Sort Code Patterns:**

- **Flash Express:** `FEX-[PROVINCE]-[CITY]-[CODE]-[RIDER]` (e.g., `FEX-BUL-SJDM-MZN1-GY01`)
- **Shopee SPX:** `[HUB]-[AREA]-[SUB]-[SEQ]` (e.g., `11-0902-3A-06`)

**Weight Distribution:**

- 60% light (100-1500g)
- 30% medium (1500-3500g)
- 10% heavy (3500-7000g)

**COD Distribution (Shopee only):**

- 70% COD parcels
- COD amounts: ₱100 - ₱5000
- Non-COD: 30%

---

## 6. GROUND TRUTH DATA STRUCTURE

### 6.1 Ground Truth JSON Format

```json
{
    "labelId": "label-FE034521A3F7G2-20250215-143022",
    "courierId": "flash-express",
    "imageFilename": "label-FE034521A3F7G2-20250215-143022.png",
    "generatedAt": "2025-02-15T14:30:22.456Z",
    "generatorVersion": "1.0.0",
    "fields": {
        "trackingNumber": {
            "value": "FE3457892341",
            "boundingBox": {"x": 120, "y": 15, "width": 180, "height": 30}
        },
        "orderId": {
            "value": "FE034521A3F7G2",
            "boundingBox": {"x": 20, "y": 80, "width": 200, "height": 20}
        },
        "sortCode": {
            "value": "FEX-BUL-SJDM-MZN1-GY01",
            "boundingBox": {"x": 20, "y": 110, "width": 280, "height": 15}
        },
        "hubCode": {
            "value": "[GY]",
            "boundingBox": {"x": 350, "y": 15, "width": 40, "height": 30}
        },
        "buyerName": {
            "value": "John Smith",
            "boundingBox": {"x": 40, "y": 220, "width": 150, "height": 15}
        },
        "buyerStreet": {
            "value": "123 Mabini St",
            "boundingBox": {"x": 40, "y": 240, "width": 150, "height": 12}
        },
        "buyerBarangay": {
            "value": "Muzon",
            "boundingBox": {"x": 40, "y": 255, "width": 80, "height": 12}
        },
        "buyerDistrict": {
            "value": "North",
            "boundingBox": {"x": 130, "y": 255, "width": 60, "height": 12}
        },
        "buyerCity": {
            "value": "San Jose del Monte",
            "boundingBox": {"x": 40, "y": 270, "width": 150, "height": 12}
        },
        "buyerProvince": {
            "value": "Bulacan",
            "boundingBox": {"x": 40, "y": 285, "width": 80, "height": 12}
        },
        "buyerZipCode": {
            "value": "3023",
            "boundingBox": {"x": 130, "y": 285, "width": 40, "height": 12}
        },
        "sellerName": {
            "value": "Flash Express",
            "boundingBox": {"x": 40, "y": 350, "width": 150, "height": 15}
        },
        "sellerAddress": {
            "value": "Gaya-Gaya Warehouse, SJDM, Bulacan 3023",
            "boundingBox": {"x": 40, "y": 370, "width": 180, "height": 24}
        },
        "weight": {
            "value": "1500g",
            "boundingBox": {"x": 30, "y": 450, "width": 60, "height": 15}
        },
        "quantity": {
            "value": "3",
            "boundingBox": {"x": 110, "y": 450, "width": 30, "height": 15}
        },
        "riderCode": {
            "value": "GY01",
            "boundingBox": {"x": 220, "y": 120, "width": 50, "height": 12}
        },
        "phNumber": {
            "value": "FE 123456789012",
            "boundingBox": {"x": 120, "y": 180, "width": 150, "height": 15}
        }
    },
    "metadata": {
        "labelDimensions": {"width": 400, "height": 600},
        "imageScale": 3,
        "compressionFormat": "png"
    }
}
```

### 6.2 Batch Manifest Format

```json
{
    "batchId": "batch-20250215-143022",
    "generatedAt": "2025-02-15T14:30:22.456Z",
    "generatorVersion": "1.0.0",
    "totalLabels": 100,
    "courierBreakdown": {
        "flash-express": 60,
        "shopee-spx": 40
    },
    "labelIds": [
        "label-FE034521A3F7G2-20250215-143022",
        "label-SPX123456789-20250215-143023",
        // ... more IDs
    ],
    "statistics": {
        "totalWeight": 125000,
        "averageWeight": 1250,
        "codParcels": 30,
        "totalCodAmount": 45000,
        "uniqueBarangays": 15,
        "uniqueDistricts": 32
    }
}
```

---

## 7. UI/UX DESIGN SPECIFICATIONS

### 7.1 Enhanced Parcel Theme UI

**Design Concept:** Clean white enterprise interface with subtle parcel/shipping visual metaphors.

**Key UI Elements:**

1. **Main Container:** Card-style with subtle box-shadow resembling a parcel
2. **Courier Selector:** Tabbed interface with courier logos
3. **Generation Controls:** Grouped buttons with clear hierarchy
4. **Label Display Grid:** Masonry-style layout with hover effects
5. **Batch Actions:** Floating action menu for bulk operations

**HTML Structure Enhancements:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Courier Parcel Generator</title>
    <!-- External libraries -->
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <!-- HERO SECTION -->
    <div class="hero-section">
        <div class="parcel-icon">📦</div>
        <h1>Multi-Courier Parcel Generator</h1>
        <p class="tagline">Generate realistic shipping labels for OCR training</p>
    </div>

    <!-- MAIN CONTAINER -->
    <div class="app-container">
        <!-- COURIER SELECTOR -->
        <div class="courier-selector">
            <h3>Select Courier</h3>
            <div class="courier-tabs">
                <button class="courier-tab active" data-courier="flash-express">
                    <img src="assets/logos/flash-express.svg" alt="Flash Express">
                    <span>Flash Express</span>
                </button>
                <button class="courier-tab" data-courier="shopee-spx">
                    <img src="assets/logos/shopee-spx.svg" alt="Shopee SPX">
                    <span>Shopee SPX</span>
                </button>
                <!-- Add more couriers here -->
            </div>
        </div>

        <!-- LOCATION CONTROLS -->
        <div class="location-controls">
            <h4>Location Settings</h4>
            <div class="control-group">
                <label for="barangaySelect">Barangay:</label>
                <select id="barangaySelect">
                    <option value="random">Random</option>
                    <!-- Populated dynamically -->
                </select>
                
                <label for="districtSelect">District:</label>
                <select id="districtSelect">
                    <option value="random">Random</option>
                    <!-- Populated dynamically -->
                </select>
            </div>
        </div>

        <!-- GENERATION CONTROLS -->
        <div class="generation-controls">
            <div class="button-row">
                <button id="generateSingle" class="btn btn-primary">
                    <span class="icon">📄</span>
                    Generate Single
                </button>
                <button id="generateBatch" class="btn btn-secondary">
                    <span class="icon">📚</span>
                    Generate Batch (5)
                </button>
                <button id="generateCustom" class="btn btn-secondary">
                    <span class="icon">⚙️</span>
                    Custom Batch...
                </button>
            </div>
            
            <div class="button-row">
                <button id="downloadAllImages" class="btn btn-success">
                    <span class="icon">💾</span>
                    Download All (PNG + JSON)
                </button>
                <button id="clearAll" class="btn btn-danger">
                    <span class="icon">🗑️</span>
                    Clear All
                </button>
            </div>
        </div>

        <!-- STATS DISPLAY -->
        <div class="stats-bar">
            <div class="stat-item">
                <span class="stat-label">Generated:</span>
                <span class="stat-value" id="totalCount">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Flash Express:</span>
                <span class="stat-value" id="flashCount">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Shopee SPX:</span>
                <span class="stat-value" id="spxCount">0</span>
            </div>
        </div>

        <!-- LABEL DISPLAY GRID -->
        <div id="labelGrid" class="label-grid">
            <!-- Labels rendered here dynamically -->
        </div>
    </div>

    <!-- TOAST NOTIFICATIONS -->
    <div id="toastContainer" class="toast-container"></div>

    <!-- LOADING OVERLAY -->
    <div id="loadingOverlay" class="loading-overlay hidden">
        <div class="spinner"></div>
        <p>Generating labels...</p>
    </div>

    <script src="core/courier-registry.js"></script>
    <script src="core/label-engine.js"></script>
    <script src="core/label-renderer.js"></script>
    <script src="core/ground-truth-exporter.js"></script>
    <script src="couriers/flash-express.js"></script>
    <script src="couriers/shopee-spx.js"></script>
    <script src="utils/data-generators.js"></script>
    <script src="utils/dictionary-extractor.js"></script>
    <script src="app.js"></script>
</body>
</html>
```

### 7.2 CSS Styling Guidelines

**Theme Colors:**

```css
:root {
    /* Primary Colors */
    --primary-color: #2c3e50;
    --secondary-color: #3498db;
    --accent-color: #e74c3c;
    
    /* Courier Brand Colors */
    --flash-orange: #ff6b35;
    --shopee-orange: #ee4d2d;
    
    /* Neutrals */
    --white: #ffffff;
    --light-gray: #f8f9fa;
    --medium-gray: #e0e0e0;
    --dark-gray: #4a4a4a;
    --black: #1a1a1a;
    
    /* Functional Colors */
    --success: #27ae60;
    --warning: #f39c12;
    --danger: #e74c3c;
    --info: #3498db;
    
    /* Shadows */
    --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.1);
    --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.12);
    --shadow-lg: 0 8px 16px rgba(0, 0, 0, 0.15);
    
    /* Borders */
    --border-radius: 8px;
    --border-color: var(--medium-gray);
}
```

**Key Styling Elements:**

```css
/* Hero Section with Parcel Icon */
.hero-section {
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    color: var(--white);
    padding: 40px 20px;
    text-align: center;
}

.parcel-icon {
    font-size: 64px;
    animation: float 3s ease-in-out infinite;
}

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

/* App Container - Parcel Box Style */
.app-container {
    max-width: 1200px;
    margin: -40px auto 40px;
    background: var(--white);
    border-radius: var(--border-radius);
    box-shadow: var(--shadow-lg);
    padding: 30px;
    position: relative;
}

/* Subtle tape effect on corners */
.app-container::before,
.app-container::after {
    content: '';
    position: absolute;
    top: 0;
    width: 60px;
    height: 40px;
    background: rgba(255, 193, 7, 0.3);
    border-radius: 4px;
}

.app-container::before {
    left: 20px;
    transform: rotate(-5deg);
}

.app-container::after {
    right: 20px;
    transform: rotate(5deg);
}

/* Courier Tabs */
.courier-tabs {
    display: flex;
    gap: 10px;
    margin-top: 15px;
}

.courier-tab {
    flex: 1;
    padding: 15px;
    background: var(--light-gray);
    border: 2px solid var(--border-color);
    border-radius: var(--border-radius);
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
}

.courier-tab:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.courier-tab.active {
    background: var(--white);
    border-color: var(--primary-color);
    box-shadow: var(--shadow-md);
}

.courier-tab img {
    height: 32px;
}

/* Label Grid with Masonry Layout */
.label-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 20px;
    margin-top: 30px;
}

.label-wrapper {
    position: relative;
    background: var(--white);
    border-radius: var(--border-radius);
    box-shadow: var(--shadow-sm);
    padding: 15px;
    transition: all 0.3s ease;
}

.label-wrapper:hover {
    box-shadow: var(--shadow-lg);
    transform: translateY(-4px);
}

/* Action Buttons Overlay */
.label-actions {
    position: absolute;
    top: 10px;
    right: 10px;
    display: flex;
    gap: 5px;
    opacity: 0;
    transition: opacity 0.3s ease;
}

.label-wrapper:hover .label-actions {
    opacity: 1;
}

.action-btn {
    background: rgba(0, 0, 0, 0.7);
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
    cursor: pointer;
    transition: background 0.2s ease;
}

.action-btn:hover {
    background: rgba(0, 0, 0, 0.9);
}

/* Toast Notifications */
.toast-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.toast {
    background: var(--white);
    padding: 15px 20px;
    border-radius: var(--border-radius);
    box-shadow: var(--shadow-lg);
    border-left: 4px solid var(--success);
    animation: slideIn 0.3s ease;
}

@keyframes slideIn {
    from {
        transform: translateX(400px);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.toast.error {
    border-left-color: var(--danger);
}

.toast.warning {
    border-left-color: var(--warning);
}

/* Loading Overlay */
.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 9998;
}

.spinner {
    width: 60px;
    height: 60px;
    border: 4px solid rgba(255, 255, 255, 0.3);
    border-top-color: var(--white);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.loading-overlay p {
    color: var(--white);
    margin-top: 20px;
    font-size: 18px;
}

/* Responsive Design */
@media (max-width: 768px) {
    .label-grid {
        grid-template-columns: 1fr;
    }
    
    .courier-tabs {
        flex-direction: column;
    }
}
```

---

## 8. INTEGRATION POINTS

### 8.1 OCR Pipeline Integration (Future)

**Headless Generation Script** (`scripts/headless-generator.js`):

```javascript
/**
 * Node.js script for headless label generation
 * Runs generator in JSDOM and POSTs images to OCR API
 */

const jsdom = require('jsdom');
const { JSDOM } = jsdom;
const fs = require('fs');
const axios = require('axios');

async function generateAndUploadBatch(count, ocrApiUrl) {
    // 1. Initialize JSDOM with generator code
    // 2. Generate labels using LabelEngine
    // 3. Capture images using html2canvas (in JSDOM)
    // 4. POST images + ground truth to OCR API
    // 5. Return upload results
}

module.exports = { generateAndUploadBatch };
```

### 8.2 Dictionary Extraction for Phase 7.7

**Usage Example:**

```javascript
// After generating 1000 labels
const allLabels = labelEngine.getGeneratedLabels();

const dictionaries = DictionaryExtractor.extractDictionaries(allLabels, [
    'barangay',
    'district',
    'riderCode',
    'hubCode',
    'sortCode'
]);

// Export for Python backend
await DictionaryExtractor.exportDictionariesAsJSON(dictionaries, 'ocr-dictionaries.json');

// Or generate Python dict directly
const pythonDict = DictionaryExtractor.generatePythonDict(dictionaries);
console.log(pythonDict);
```

**Output Format (JSON):**

```json
{
    "barangay": ["Muzon", "Tungko", "Sapang Palay", "Gaya-Gaya", "Graceville"],
    "district": ["North", "South", "Central", "West", "East", "Main", "Subdivision"],
    "riderCode": ["GY01", "GY02", "GY03", "GY04", "GY05"],
    "hubCode": ["[GY]", "[HUB]", "[FEX]"],
    "sortCode": [
        "FEX-BUL-SJDM-MZN1-GY01",
        "FEX-BUL-SJDM-MZN2-GY02",
        "11-0902-3A-06",
        "11-0902-3B-12"
    ]
}
```

---

## 9. CONSTRAINTS & VALIDATION

### 9.1 System Constraints

1. **Browser Compatibility:**
   - Chrome/Edge: v90+
   - Firefox: v88+
   - Safari: v14+
   - No IE support

2. **Performance Requirements:**
   - Single label generation: <500ms
   - Batch of 10 labels: <5 seconds
   - Batch of 100 labels: <60 seconds
   - Image capture (html2canvas): <2 seconds per label

3. **Memory Limits:**
   - Maximum concurrent labels in DOM: 200
   - ZIP file size limit: 500MB
   - Individual image size: <5MB

4. **File Format Standards:**
   - Images: PNG (default), JPEG (optional)
   - Ground truth: JSON (UTF-8)
   - Barcodes: Code 128 format
   - QR codes: Version 4 or higher

### 9.2 Validation Rules

**Label Data Validation:**

```javascript
function validateLabelData(labelData, courierConfig) {
    const errors = [];
    
    // Required fields check
    for (const field of courierConfig.layout.requiredFields) {
        if (!labelData[field]) {
            errors.push(`Missing required field: ${field}`);
        }
    }
    
    // Tracking number format
    if (!courierConfig.validation.trackingNumberPattern.test(labelData.trackingNumber)) {
        errors.push(`Invalid tracking number format: ${labelData.trackingNumber}`);
    }
    
    // Weight validation
    if (labelData.weight > courierConfig.validation.maxWeight) {
        errors.push(`Weight exceeds maximum: ${labelData.weight}g > ${courierConfig.validation.maxWeight}g`);
    }
    
    // Address completeness
    for (const addressField of courierConfig.validation.requiredAddressFields) {
        if (!labelData.buyerAddress[addressField]) {
            errors.push(`Missing buyer address field: ${addressField}`);
        }
    }
    
    return {
        valid: errors.length === 0,
        errors: errors,
        warnings: [] // Optional warnings
    };
}
```

---

## 10. ERROR HANDLING

### 10.1 Error Categories

**Category 1: Configuration Errors**

```javascript
// Courier not registered
throw new Error(`Courier '${courierId}' is not registered. Available: ${availableCouriers.join(', ')}`);

// Invalid courier config
throw new Error(`Invalid courier configuration for '${courierId}': ${validationErrors.join('; ')}`);
```

**Category 2: Generation Errors**

```javascript
// Data generation failure
throw new Error(`Failed to generate ${fieldName}: ${error.message}`);

// Validation failure
throw new Error(`Label validation failed: ${validationResult.errors.join('; ')}`);
```

**Category 3: Rendering Errors**

```javascript
// DOM rendering failure
throw new Error(`Failed to render label ${labelId}: ${error.message}`);

// Image capture failure
throw new Error(`Failed to capture label ${labelId} as image: ${error.message}`);
```

**Category 4: Export Errors**

```javascript
// ZIP creation failure
throw new Error(`Failed to create ZIP archive: ${error.message}`);

// Ground truth export failure
throw new Error(`Failed to export ground truth for ${labelId}: ${error.message}`);
```

### 10.2 Error Recovery Strategies

1. **Retry with Exponential Backoff:** For transient failures (image capture, network)
2. **Fallback to Defaults:** For missing optional data
3. **Skip and Continue:** For batch operations (log failures, continue with next)
4. **User Notification:** Display error toast with actionable message

---

## 11. TEST PLAN OUTLINE

### 11.1 Visual Fidelity Tests

**Test 1: Flash Express Label Accuracy**

- **Objective:** Verify generated label matches real Flash Express receipts
- **Method:** Side-by-side comparison with actual receipt photos
- **Success Criteria:**
  - Layout structure matches (header, sections, footer)
  - Font sizes and weights are accurate
  - Colors match brand guidelines
  - Barcode/QR placement is correct

**Test 2: Shopee SPX Label Accuracy**

- **Objective:** Verify Shopee SPX template matches specification PDF
- **Method:** Compare with Shopee SPX Air Waybill spec document
- **Success Criteria:**
  - All required fields present (no phone numbers)
  - Sort code and route code formats correct
  - Tagline text matches exactly
  - COD highlighting works

### 11.2 Ground Truth Validation Tests

**Test 3: Ground Truth Completeness**

- **Objective:** Ensure every text field on label has corresponding ground truth entry
- **Method:** Automated script to compare rendered label text with JSON
- **Success Criteria:**
  - 100% field coverage
  - No missing values
  - Values match exactly (no OCR errors in ground truth)

**Test 4: Bounding Box Accuracy** (Future Enhancement)

- **Objective:** Validate bounding box coordinates for OCR
- **Method:** Visual overlay of bounding boxes on images
- **Success Criteria:**
  - Boxes tightly encompass text
  - No overlap with adjacent fields
  - Margin of error: <5 pixels

### 11.3 Functional Tests

**Test 5: Batch Generation Performance**

- **Objective:** Verify system handles large batches efficiently
- **Test Cases:**
  - 10 labels: <5 seconds
  - 50 labels: <30 seconds
  - 100 labels: <60 seconds
- **Success Criteria:** Performance within specified limits

**Test 6: Courier Switching**

- **Objective:** Ensure courier switching works without errors
- **Method:** Generate labels alternating between couriers
- **Success Criteria:**
  - No layout bleeding between couriers
  - Correct templates applied
  - Data generators match courier

**Test 7: ZIP Export Integrity**

- **Objective:** Verify ZIP download contains all files
- **Method:** Generate batch, download ZIP, extract and validate
- **Success Criteria:**
  - All images present (N images)
  - All ground truth JSON present (N files)
  - Manifest.json correct
  - Files not corrupted

### 11.4 Data Validation Tests

**Test 8: Tracking Number Uniqueness**

- **Objective:** Ensure no duplicate tracking numbers in batch
- **Method:** Generate 1000 labels, check for duplicates
- **Success Criteria:** 0 duplicates

**Test 9: Address Dictionary Coverage**

- **Objective:** Verify address data is realistic and diverse
- **Method:** Generate 500 labels, analyze address distribution
- **Success Criteria:**
  - At least 10 unique barangays
  - At least 20 unique districts
  - At least 30 unique streets
  - No malformed addresses

---

## 12. IMPLEMENTATION PHASES

### Phase 1: Core Architecture (Week 1)

- [ ] Create directory structure
- [ ] Implement `CourierRegistry` class
- [ ] Implement `LabelEngine` class (basic)
- [ ] Implement `LabelRenderer` class (basic)
- [ ] Unit tests for core classes

### Phase 2: Flash Express Refactor (Week 1-2)

- [ ] Refactor existing Flash Express code into modular structure
- [ ] Extract Flash Express configuration
- [ ] Migrate existing HTML template to template function
- [ ] Test existing functionality preservation

### Phase 3: Shopee SPX Implementation (Week 2-3)

- [ ] Design Shopee SPX HTML template
- [ ] Implement Shopee SPX CSS styling
- [ ] Create Shopee SPX data generators
- [ ] Implement COD logic
- [ ] Visual fidelity testing

### Phase 4: Ground Truth Export (Week 3)

- [ ] Implement `GroundTruthExporter` class
- [ ] Create ground truth JSON structure
- [ ] Integrate JSZip for batch download
- [ ] Generate manifest files
- [ ] Test ZIP export

### Phase 5: UI Enhancement (Week 4)

- [ ] Redesign HTML with parcel theme
- [ ] Implement courier selector tabs
- [ ] Create enhanced controls
- [ ] Add toast notifications
- [ ] Responsive design

### Phase 6: Dictionary Extraction (Week 4)

- [ ] Implement `DictionaryExtractor` utility
- [ ] Create extraction logic
- [ ] Add Python dict export
- [ ] Integration testing

### Phase 7: Testing & Refinement (Week 5)

- [ ] Visual fidelity tests
- [ ] Performance optimization
- [ ] Bug fixes
- [ ] Documentation updates

---

## 13. ACCEPTANCE CRITERIA

### Functional Requirements

✅ **FR1:** System supports at least 2 couriers (Flash Express, Shopee SPX)
✅ **FR2:** Each courier has unique template, branding, and data generators
✅ **FR3:** User can switch between couriers via UI
✅ **FR4:** User can generate single or batch labels (up to 100)
✅ **FR5:** Generated labels are visually accurate to real receipts
✅ **FR6:** System exports ground truth JSON for each label
✅ **FR7:** Batch export creates ZIP with images + JSON + manifest
✅ **FR8:** Dictionary extraction utility works for specified fields
✅ **FR9:** UI is clean, modern, and responsive

### Non-Functional Requirements

✅ **NFR1:** Single label generation completes in <500ms
✅ **NFR2:** Batch of 10 labels completes in <5 seconds
✅ **NFR3:** System handles 100-label batches without crashes
✅ **NFR4:** Code is modular and extensible (easy to add new couriers)
✅ **NFR5:** Ground truth data is 100% accurate (no discrepancies)
✅ **NFR6:** UI is accessible on desktop and tablet
✅ **NFR7:** No console errors in production

### Technical Requirements

✅ **TR1:** All code uses ES6+ JavaScript standards
✅ **TR2:** No external frameworks (React, Vue, etc.) - vanilla JS only
✅ **TR3:** All external libraries loaded via CDN
✅ **TR4:** Code is well-documented with JSDoc comments
✅ **TR5:** File structure follows specified directory layout
✅ **TR6:** All interfaces match contract specifications

---

## 14. DEPENDENCIES

### External Libraries (CDN)

```html
<!-- Image Capture -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>

<!-- Barcode Generation -->
<script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>

<!-- QR Code Generation -->
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>

<!-- ZIP File Creation -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>

<!-- PDF Export (Optional) -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
```

### Internal Module Dependencies

```
app.js
├── core/courier-registry.js
├── core/label-engine.js (depends on courier-registry)
├── core/label-renderer.js (depends on html2canvas, JsBarcode, QRCode)
├── core/ground-truth-exporter.js (depends on label-renderer, JSZip)
├── couriers/flash-express.js (depends on courier-registry)
├── couriers/shopee-spx.js (depends on courier-registry)
└── utils/dictionary-extractor.js
```

---

## 15. MIGRATION FROM EXISTING CODE

### 15.1 Code Mapping

**Existing `app.js` → New Structure:**

| Old Function/Code | New Location | Notes |
|------------------|--------------|-------|
| `getRandomOrderID()` | `utils/data-generators.js` | Make generic |
| `getRandomTrackingNumber()` | `couriers/flash-express.js` | Courier-specific |
| `getRandomBuyerName()` | `utils/data-generators.js` | Shared utility |
| `getRandomAddress()` | `utils/data-generators.js` + data files | Load from JSON |
| `getRTSCode()` | `couriers/flash-express.js` | Courier-specific |
| `generateQRCode()` | `utils/barcode-utils.js` | Wrapper utility |
| `exportImage()` | `core/label-renderer.js` | Method: `captureAsImage()` |
| Label HTML | `couriers/flash-express.js` | Template function |
| Barangay data | `data/metro-manila-addresses.json` | Structured JSON |

### 15.2 Preserved Functionality

All existing Flash Express generator functionality must be preserved:

- ✅ RTS sort code generation logic
- ✅ Location-specific district mappings
- ✅ Barangay/district selector dropdowns
- ✅ Weight and quantity generation
- ✅ Barcode and QR code generation
- ✅ PDF export capability
- ✅ Label visual design (colors, layout, fonts)

---

## 16. FUTURE EXTENSIBILITY

### 16.1 Adding New Couriers

**Step-by-Step Guide:**

1. Create `couriers/[new-courier].js` based on `courier-template.js`
2. Define courier configuration object
3. Implement data generators (tracking, order ID, sort codes)
4. Create HTML template function
5. Add CSS styles to `styles.css`
6. Add logo to `assets/logos/`
7. Register courier in `app.js`: `courierRegistry.registerCourier(NEW_COURIER_CONFIG)`
8. Update UI courier selector
9. Test visual fidelity and data generation

**Estimated time per new courier:** 4-8 hours (depending on complexity)

### 16.2 Planned Future Couriers

- J&T Express
- LBC Express
- Ninja Van
- Lalamove
- Grab Express

---

## 17. DOCUMENTATION REQUIREMENTS

### 17.1 Developer Documentation

- **README.md:** Project overview, setup instructions, usage guide
- **ARCHITECTURE.md:** System architecture diagram and explanation
- **API_REFERENCE.md:** Full JSDoc-generated API reference
- **COURIER_GUIDE.md:** Guide for adding new couriers

### 17.2 User Documentation

- **USER_GUIDE.md:** End-user manual with screenshots
- **FAQ.md:** Common questions and troubleshooting

---

## 18. POST-IMPLEMENTATION CHECKLIST

**Before Handoff to Production:**

- [ ] All unit tests pass
- [ ] Visual fidelity tests pass for both couriers
- [ ] Ground truth validation passes (100% accuracy)
- [ ] Performance benchmarks met
- [ ] Code review completed
- [ ] Documentation completed
- [ ] Browser compatibility tested
- [ ] Accessibility audit passed
- [ ] No console errors or warnings
- [ ] ZIP export tested with 100+ labels
- [ ] Dictionary extraction tested
- [ ] UI responsive on mobile/tablet
- [ ] All external CDN links verified

---

## 19. CONTACT & SUPPORT

**Primary Developer:** [Your Name]
**Project Repository:** [GitHub URL]
**Issue Tracker:** [GitHub Issues URL]
**Documentation:** [Docs URL]

---

**END OF CONTRACT**

---

## APPENDIX A: Sample Courier Configuration Template

```javascript
/**
 * Template for adding a new courier
 * Copy this file to couriers/[courier-name].js and customize
 */

const NEW_COURIER_CONFIG = {
    id: 'courier-id', // Unique, lowercase, hyphen-separated
    name: 'Courier Display Name',
    branding: {
        primaryColor: '#000000',
        secondaryColor: '#ffffff',
        logoPath: 'assets/logos/courier-logo.svg',
        tagline: 'Courier Tagline or Slogan',
        fontFamily: 'Arial, sans-serif'
    },
    generators: {
        trackingNumber: () => {
            // Return unique tracking number string
            // Example: PREFIX + random digits
        },
        orderId: () => {
            // Return unique order ID string
        },
        sortCode: (barangay, district) => {
            // Return sort code based on location
        },
        hubCode: () => {
            // Return hub identifier
        },
        phNumber: () => {
            // Return barcode number
        },
        weight: () => {
            // Return weight in grams
        },
        quantity: (weight) => {
            // Return item quantity based on weight
        }
    },
    layout: {
        templateFunction: (data) => {
            // Return HTML string for label
            return `<div class="shipping-label ${this.id}-label">
                <!-- Your label HTML here -->
            </div>`;
        },
        cssClassName: 'courier-id-label',
        dimensions: { width: 400, height: 600 },
        requiredFields: [
            'trackingNumber',
            'orderId',
            // ... other required fields
        ]
    },
    dataDictionaries: {
        barangays: [],
        districts: {},
        streets: [],
        cities: [],
        provinces: []
    },
    validation: {
        maxWeight: 7000,
        trackingNumberPattern: /^[A-Z]{2,3}\d{9,12}$/,
        orderIdPattern: /^[A-Z0-9]{10,15}$/,
        requiredAddressFields: ['street', 'barangay', 'city', 'province', 'zipCode']
    }
};
```

---

**Version History:**

- v1.0 (2025-02-15) - Initial contract draft