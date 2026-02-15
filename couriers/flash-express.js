/**
 * Flash Express courier configuration
 * Based on existing implementation in app.js
 */

const FLASH_EXPRESS_CONFIG = {
    id: 'flash-express',
    name: 'Flash Express',
    branding: {
        primaryColor: '#ff6b35',
        secondaryColor: '#e55a2b',
        logoPath: 'assets/logos/flash-express.svg',
        tagline: 'FASTEST DELIVERY IN THE PHILIPPINES',
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
            // RTS code logic from app.js
            const rtsMap = {
                Muzon: {
                    North: "FEX-BUL-SJDM-MZN1-GY01",
                    South: "FEX-BUL-SJDM-MZN2-GY02",
                    Central: "FEX-BUL-SJDM-MZN3-GY03",
                    Proper: "FEX-BUL-SJDM-MZN4-GY04"
                },
                Graceville: {
                    Subdivision: "FEX-BUL-SJDM-GRC1-GY05",
                    Main: "FEX-BUL-SJDM-GRC2-GY06",
                    Commercial: "FEX-BUL-SJDM-GRC3-GY07"
                },
                "Poblacion I": {
                    "Central District": "FEX-BUL-SJDM-POB1-GY08",
                    Downtown: "FEX-BUL-SJDM-POB2-GY09",
                    Main: "FEX-BUL-SJDM-POB3-GY10"
                },
                "Loma de Gato": {
                    "Marilao Border": "FEX-BUL-SJDM-LDG1-GY11",
                    Residential: "FEX-BUL-SJDM-LDG2-GY12",
                    Main: "FEX-BUL-SJDM-LDG3-GY13"
                },
                "Bagong Silang (Brgy 176)": {
                    "Caloocan Border": "FEX-BUL-SJDM-BS01-GY14",
                    "Metro Manila Border": "FEX-BUL-SJDM-BS02-GY15",
                    Main: "FEX-BUL-SJDM-BS03-GY16"
                },
                "Gaya-Gaya": {
                    "Warehouse District": "FEX-BUL-SJDM-GYG1-HUB",
                    Main: "FEX-BUL-SJDM-GYG2-GY17",
                    Central: "FEX-BUL-SJDM-GYG3-GY18"
                },
                "Sapang Palay": {
                    West: "FEX-BUL-SJDM-SPY1-GY19",
                    East: "FEX-BUL-SJDM-SPY2-GY20",
                    Central: "FEX-BUL-SJDM-SPY3-GY21"
                },
                Tungko: {
                    Main: "FEX-BUL-SJDM-TKO1-GY22",
                    Subdivision: "FEX-BUL-SJDM-TKO2-GY23"
                }
            };
            return rtsMap[barangay]?.[district] || "FEX-UNKNOWN";
        },
        hubCode: () => {
            const codes = ["[GY]", "[HUB]", "[FEX]"];
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
            // HTML template matching the existing Flash Express label design
            return `
                <div class="header">
                    <div class="flash-logo">FLASH<br><small style="font-size: 8px;">EXPRESS</small></div>
                    <div class="tracking-number">${data.trackingNumber}</div>
                    <div class="hub-code">${data.hubCode}</div>
                </div>

                <div class="rts-info">
                    <div>FEX-GAYA-GAYA-HUB-SJDM</div>
                    <div>RTS Sort Code:</div>
                    <div>${data.sortCode}</div>
                    <div>Rider: ${data.riderCode || ''}</div>
                </div>

                <div class="order-section">
                    <div class="order-id">Order ID: <span>${data.orderId}</span></div>
                </div>

                <div class="barcode-section">
                    <div class="barcode-container">
                        <svg class="barcode" id="barcode-${data.orderId}"></svg>
                    </div>
                    <div class="ph-number">${data.phNumber}</div>
                </div>

                <div class="address-section">
                    <div class="buyer-section">
                        <svg class="section-label" width="20" height="60" viewBox="0 0 20 60">
                            <rect width="20" height="60" fill="#000" />
                            <text x="10" y="30" transform="rotate(-90 10 30)" dominant-baseline="middle" text-anchor="middle" font-size="10" fill="white" font-family="Arial">BUYER</text>
                        </svg>
                        <div class="address-content">
                            <div class="name">${data.buyerName}</div>
                            <div>${data.buyerAddress.full}</div>
                            <br>
                            <div style="display: flex; justify-content: space-between; font-size: 8px;">
                                <div>District<br>Street</div>
                                <div>City<br>Province</div>
                                <div>Zip Code</div>
                            </div>
                        </div>
                        <div style="position: absolute; right: 10px; top: 10px; font-weight: bold;">PDG</div>
                    </div>
                </div>

                <div class="address-section">
                    <div class="seller-section">
                        <svg class="section-label" width="20" height="60" viewBox="0 0 20 60">
                            <rect width="20" height="60" fill="#000" />
                            <text x="10" y="30" transform="rotate(-90 10 30)" dominant-baseline="middle" text-anchor="middle" font-size="10" fill="white" font-family="Arial">SELLER</text>
                        </svg>
                        <div class="address-content">
                            <div class="name">${data.sellerName}</div>
                            <div>${data.sellerAddress.full}</div>
                            <br>
                            <div style="display: flex; justify-content: space-between; font-size: 8px;">
                                <div>District<br>Street</div>
                                <div>City<br>Province</div>
                                <div>Zip Code</div>
                            </div>
                        </div>
                        <div style="position: absolute; right: 10px; top: 10px; font-weight: bold;">COD</div>
                    </div>
                </div>

                <div class="cod-section">
                    <div class="product-info">
                        <div>Product Quantity: <span>${data.quantity}</span></div>
                        <div>Weight: <span>${data.weight}g</span></div>
                    </div>
                    
                    <div class="qr-section">
                        <div class="qr-code" id="qr-${data.orderId}"></div>
                    </div>
                    
                    <div class="delivery-attempts">
                        <div style="font-size: 8px;">Delivery Attempt</div>
                        <div class="attempt-boxes">
                            <div class="attempt-box">1</div>
                            <div class="attempt-box">2</div>
                            <div class="attempt-box">3</div>
                        </div>
                    </div>
                    
                    <div class="delivery-attempts">
                        <div style="font-size: 8px;">Return Attempt</div>
                        <div class="attempt-boxes">
                            <div class="attempt-box">1</div>
                            <div class="attempt-box">2</div>
                            <div class="attempt-box">3</div>
                        </div>
                    </div>
                </div>

                <div class="footer">
                    FASTEST DELIVERY IN THE PHILIPPINES
                    <div class="guarantee-text">WITH ON-TIME DELIVERY GUARANTEE</div>
                </div>
            `;
        },
        cssClassName: 'flash-express-label',
        dimensions: { width: 400, height: 600 },
        requiredFields: [
            'trackingNumber', 'orderId', 'sortCode', 'hubCode',
            'buyerName', 'buyerAddress', 'sellerName', 'sellerAddress',
            'weight', 'quantity', 'phNumber'
        ]
    },
    dataDictionaries: {
        barangays: [
            "Muzon", "Graceville", "Poblacion I", "Loma de Gato",
            "Bagong Silang (Brgy 176)", "Gaya-Gaya", "Sapang Palay", "Tungko"
        ],
        districts: {
            "Muzon": [
                { name: "North", code: "MZN1" },
                { name: "South", code: "MZN2" },
                { name: "Central", code: "MZN3" },
                { name: "Proper", code: "MZN4" }
            ],
            "Graceville": [
                { name: "Subdivision", code: "GRC1" },
                { name: "Main", code: "GRC2" },
                { name: "Commercial", code: "GRC3" }
            ],
            "Poblacion I": [
                { name: "Central District", code: "POB1" },
                { name: "Downtown", code: "POB2" },
                { name: "Main", code: "POB3" }
            ],
            "Loma de Gato": [
                { name: "Marilao Border", code: "LDG1" },
                { name: "Residential", code: "LDG2" },
                { name: "Main", code: "LDG3" }
            ],
            "Bagong Silang (Brgy 176)": [
                { name: "Caloocan Border", code: "BS01" },
                { name: "Metro Manila Border", code: "BS02" },
                { name: "Main", code: "BS03" }
            ],
            "Gaya-Gaya": [
                { name: "Warehouse District", code: "GYG1" },
                { name: "Main", code: "GYG2" },
                { name: "Central", code: "GYG3" }
            ],
            "Sapang Palay": [
                { name: "West", code: "SPY1" },
                { name: "East", code: "SPY2" },
                { name: "Central", code: "SPY3" }
            ],
            "Tungko": [
                { name: "Main", code: "TKO1" },
                { name: "Subdivision", code: "TKO2" }
            ]
        },
        streets: [
            "Mabini St", "Rizal Ave", "Bonifacio St", "Mabuhay St", "Del Pilar St",
            "Kalayaan Ave", "Maginhawa St", "Kamuning Rd", "Tandang Sora Ave", "Sto. Domingo St",
            "Sta. Mesa St", "España Blvd", "Lacson Ave", "Vicente Cruz St", "Carriedo St",
            "NLEX Service Rd", "Del Monte Ave", "Bulacan Highway", "Main Street"
        ],
        cities: ["San Jose del Monte"],
        provinces: ["Bulacan"]
    },
    validation: {
        maxWeight: 7000,
        trackingNumberPattern: /^FE\d{10}$/,
        orderIdPattern: /^FE\d{6}[A-Z0-9]{6}$/,
        requiredAddressFields: ['street', 'barangay', 'district', 'city', 'province', 'zipCode']
    }
};

// For backward compatibility, also expose the barangays array if needed elsewhere
if (typeof window !== 'undefined') {
    window.flashExpressBarangays = FLASH_EXPRESS_CONFIG.dataDictionaries.barangays;
    window.flashExpressDistricts = FLASH_EXPRESS_CONFIG.dataDictionaries.districts;
}