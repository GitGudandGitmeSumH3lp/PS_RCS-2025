/**
 * @namespace DictionaryExtractor
 * @description Utility functions for extracting dictionaries from generated labels
 */
const DictionaryExtractor = {
    /**
     * Extract all unique values for specified fields
     * @param {LabelData[]} labelDataArray - Array of label data
     * @param {string[]} fieldNames - Fields to extract (dot notation supported, e.g., 'buyerAddress.barangay')
     * @returns {Object.<string, string[]>} Dictionary object with field -> unique values
     */
    extractDictionaries(labelDataArray, fieldNames) {
        const dictionaries = {};

        for (const fieldName of fieldNames) {
            const uniqueValues = new Set();

            for (const labelData of labelDataArray) {
                const value = this._getNestedValue(labelData, fieldName);
                if (value !== undefined && value !== null && value !== '') {
                    uniqueValues.add(String(value));
                }
            }

            dictionaries[fieldName] = Array.from(uniqueValues).sort();
        }

        return dictionaries;
    },

    /**
     * Get nested value from object using dot notation
     * @param {Object} obj - Object to traverse
     * @param {string} path - Dot-separated path
     * @returns {*} Value at path or undefined
     * @private
     */
    _getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => {
            return current && current[key] !== undefined ? current[key] : undefined;
        }, obj);
    },

    /**
     * Export dictionaries as JSON file
     * @param {Object.<string, string[]>} dictionaries - Extracted dictionaries
     * @param {string} [filename='dictionaries.json'] - Output filename
     * @returns {Promise<void>}
     */
    async exportDictionariesAsJSON(dictionaries, filename = 'dictionaries.json') {
        const jsonString = JSON.stringify(dictionaries, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
    },

    /**
     * Generate Python-compatible dictionary format
     * @param {Object.<string, string[]>} dictionaries - Extracted dictionaries
     * @returns {string} Python dict literal as string
     */
    generatePythonDict(dictionaries) {
        let pythonDict = '{\n';
        for (const [key, values] of Object.entries(dictionaries)) {
            pythonDict += `    "${key}": [\n`;
            for (const value of values) {
                // Escape quotes
                const escaped = value.replace(/"/g, '\\"');
                pythonDict += `        "${escaped}",\n`;
            }
            pythonDict += `    ],\n`;
        }
        pythonDict += '}';
        return pythonDict;
    }
};