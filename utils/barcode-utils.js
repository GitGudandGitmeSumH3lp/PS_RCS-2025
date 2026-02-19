# MERGED FILE: src/frontend/static/js/barcode-utils.js
/**
 * @namespace BarcodeUtils
 * @description Wrapper utilities for barcode and QR code generation
 */

const BarcodeUtils = {
    /**
     * Generate a barcode inside an element
     * @param {string} elementId - ID of the container element (should be an SVG)
     * @param {string} value - Value to encode
     * @param {Object} [options] - JsBarcode options
     */
    generateBarcode(elementId, value, options = {}) {
        const element = document.getElementById(elementId);
        if (!element) {
            throw new Error(`Element with ID '${elementId}' not found`);
        }
        if (typeof JsBarcode === 'undefined') {
            throw new Error('JsBarcode library not loaded');
        }
        try {
            JsBarcode(element, value, {
                format: 'CODE128',
                displayValue: true,
                fontSize: 14,
                width: 2.5,
                height: 60,
                margin: 5,
                ...options
            });
        } catch (e) {
            throw new Error(`Barcode generation failed: ${e.message}`);
        }
    },

    /**
     * Generate a QR code inside an element
     * @param {string} elementId - ID of container element (div)
     * @param {string} value - Value to encode
     * @param {Object} [options] - QRCode options
     */
    generateQRCode(elementId, value, options = {}) {
        const element = document.getElementById(elementId);
        if (!element) {
            throw new Error(`Element with ID '${elementId}' not found`);
        }
        if (typeof QRCode === 'undefined') {
            throw new Error('QRCode library not loaded');
        }
        // Clear previous content
        element.innerHTML = '';
        try {
            new QRCode(element, {
                text: value,
                width: 60,
                height: 60,
                correctLevel: QRCode.CorrectLevel.H,
                ...options
            });
        } catch (e) {
            throw new Error(`QR code generation failed: ${e.message}`);
        }
    }
};