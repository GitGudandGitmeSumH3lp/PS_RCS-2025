-- Flash Express Receipt Scans Database Schema
--
-- This schema defines the structure for storing OCR results from thermal receipts.
-- It enforces strict data constraints to match system contracts and research findings.
--
-- Version: 1.1 (Reconciled)
-- Created: 2026-02-09

CREATE TABLE IF NOT EXISTS receipt_scans (
    scan_id INTEGER PRIMARY KEY,         -- Unique integer ID based on timestamp
    tracking_id TEXT,                    -- Extracted FE tracking number
    order_id TEXT,                       -- Extracted FE order ID
    rts_code TEXT,                       -- Return-to-Sender sort code
    rider_id TEXT,                       -- Rider identifier
    buyer_name TEXT,                     -- Parsed buyer name
    buyer_address TEXT,                  -- Parsed or raw buyer address
    weight_g INTEGER,                    -- Package weight in grams
    quantity INTEGER,                    -- Package quantity
    payment_type TEXT,                   -- COD, Paid, or Prepaid
    confidence REAL NOT NULL,            -- OCR confidence score (0.0 - 1.0)
    raw_text TEXT NOT NULL,              -- Complete raw text from OCR
    engine TEXT NOT NULL,                -- Engine used ('tesseract' or 'paddle')
    timestamp TEXT NOT NULL,             -- ISO8601 timestamp
    scan_datetime TEXT,                  -- Field for analytics
    processing_time_ms INTEGER,          -- Processing duration in ms
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Validation constraints (from contract)
    CHECK (confidence >= 0.0 AND confidence <= 1.0),
    CHECK (weight_g IS NULL OR weight_g >= 0),
    CHECK (quantity IS NULL OR quantity >= 0),
    -- Additional constraint from research
    CHECK (processing_time_ms IS NULL OR processing_time_ms >= 0)
);

-- Indexes for performance optimization on common query paths
CREATE INDEX IF NOT EXISTS idx_tracking_id ON receipt_scans(tracking_id);
CREATE INDEX IF NOT EXISTS idx_rts_code ON receipt_scans(rts_code);
CREATE INDEX IF NOT EXISTS idx_timestamp ON receipt_scans(timestamp);

-- Additional indexes from research for performance
CREATE INDEX IF NOT EXISTS idx_rider_id ON receipt_scans(rider_id);
CREATE INDEX IF NOT EXISTS idx_created_at ON receipt_scans(created_at);
-- Partial index for high-confidence scans (analytics optimization)
CREATE INDEX IF NOT EXISTS idx_confidence ON receipt_scans(confidence) WHERE confidence > 0.7;

-- View: Recent Successful Scans
-- Simplifies querying for the frontend dashboard
CREATE VIEW IF NOT EXISTS vw_recent_successful_scans AS
SELECT 
    scan_id,
    timestamp,
    tracking_id,
    order_id,
    buyer_name,
    confidence,
    processing_time_ms,
    engine
FROM receipt_scans
WHERE confidence > 0.7
ORDER BY timestamp DESC;

-- View: Scan Statistics
-- Aggregates daily metrics for performance monitoring
CREATE VIEW IF NOT EXISTS vw_scan_statistics AS
SELECT 
    DATE(timestamp) as scan_date,
    COUNT(*) as total_scans,
    AVG(confidence) as avg_confidence,
    AVG(processing_time_ms) as avg_processing_time,
    COUNT(DISTINCT tracking_id) as unique_tracking_ids,
    COUNT(DISTINCT rider_id) as unique_riders
FROM receipt_scans
GROUP BY DATE(timestamp);