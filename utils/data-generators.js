/**
 * @namespace DataGenerators
 * @description Shared data generation utilities used across couriers
 */
const DataGenerators = {
    /**
     * Generate a random buyer/seller name
     * @returns {string}
     */
    getRandomName() {
        const firstNames = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emma', 'Chris', 'Lisa', 'James', 'Maria', 'Robert', 'Jennifer', 'William', 'Linda', 'Thomas', 'Jose', 'Ana', 'Carlos', 'Rosa', 'Miguel'];
        const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Santos', 'Cruz', 'Reyes', 'Flores', 'Morales'];
        return `${firstNames[Math.floor(Math.random() * firstNames.length)]} ${lastNames[Math.floor(Math.random() * lastNames.length)]}`;
    },

    /**
     * Generate random weight (grams)
     * @param {number} [max=7000] - Maximum weight
     * @returns {number}
     */
    getRandomWeight(max = 7000) {
        return Math.floor(Math.random() * max) + 100;
    },

    /**
     * Generate quantity based on weight (approx 500g per item)
     * @param {number} weight - Weight in grams
     * @returns {number}
     */
    getRandomQuantity(weight) {
        return Math.max(1, Math.floor(weight / 500));
    },

    /**
     * Generate a random street name (from global streets array if available)
     * @returns {string}
     */
    getRandomStreet() {
        if (window.streets && window.streets.length > 0) {
            return window.streets[Math.floor(Math.random() * window.streets.length)];
        }
        // Fallback
        return `${Math.floor(Math.random() * 500) + 1} Mabini St`;
    },

    /**
     * Generate a random barangay (from global barangays array if available)
     * @returns {string}
     */
    getRandomBarangay() {
        if (window.barangays && window.barangays.length > 0) {
            return window.barangays[Math.floor(Math.random() * window.barangays.length)];
        }
        return 'Muzon';
    },

    /**
     * Generate a random district for a given barangay (from global districts mapping)
     * @param {string} barangay - Barangay name
     * @returns {string}
     */
    getRandomDistrict(barangay) {
        if (window.districts && window.districts[barangay]) {
            const districts = window.districts[barangay];
            return districts[Math.floor(Math.random() * districts.length)];
        }
        return 'Central';
    },

    /**
     * Generate a random city (from global cities array)
     * @returns {string}
     */
    getRandomCity() {
        if (window.cities && window.cities.length > 0) {
            return window.cities[Math.floor(Math.random() * window.cities.length)];
        }
        return 'San Jose del Monte';
    },

    /**
     * Generate a random province (from global provinces array)
     * @returns {string}
     */
    getRandomProvince() {
        if (window.provinces && window.provinces.length > 0) {
            return window.provinces[Math.floor(Math.random() * window.provinces.length)];
        }
        return 'Bulacan';
    },

    /**
     * Generate a random zip code (simplified)
     * @returns {string}
     */
    getRandomZipCode() {
        return (Math.floor(Math.random() * 9000) + 1000).toString();
    }
};