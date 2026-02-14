import os
import sqlite3
from pathlib import Path

def clean_timestamps():
    """Clean up rows with missing timestamps in the receipt_scans table."""
    
    # Determine database path
    db_path_env = os.environ.get('SCANS_DB_PATH') or os.environ.get('DATABASE_URL')
    if db_path_env and db_path_env.startswith('sqlite:///'):
        db_path = db_path_env[10:]  # Remove 'sqlite:///' prefix
    elif db_path_env:
        db_path = db_path_env
    else:
        # Default path - check common locations
        possible_paths = [
            'scans.db',
            'data/database.db',
            'data/scans.db',
            os.path.join('data', 'database.db'),
            os.path.join('..', 'data', 'database.db'),
            'database.db'
        ]
        
        db_path = None
        for path in possible_paths:
            if os.path.exists(path):
                db_path = path
                break
        
        if not db_path:
            # Default fallback
            db_path = 'scans.db'
            print(f"No database found in common locations, assuming default: {db_path}")
    
    print(f"Using database file: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='receipt_scans';
        """)
        
        if not cursor.fetchone():
            print("Table 'receipt_scans' does not exist. Nothing to clean.")
            conn.close()
            return
        
        # Count total rows before cleanup
        cursor.execute("SELECT COUNT(*) FROM receipt_scans;")
        total_before = cursor.fetchone()[0]
        
        # Delete rows with NULL or empty timestamp
        cursor.execute("""
            DELETE FROM receipt_scans 
            WHERE timestamp IS NULL OR timestamp = '';
        """)
        
        rows_deleted = cursor.rowcount
        
        # Commit changes
        conn.commit()
        
        # Count remaining rows after cleanup
        cursor.execute("SELECT COUNT(*) FROM receipt_scans;")
        total_after = cursor.fetchone()[0]
        
        print(f"Rows deleted: {rows_deleted}")
        print(f"Remaining rows: {total_after}")
        print(f"Total rows before cleanup: {total_before}")
        
        conn.close()
        print("Database cleanup completed successfully!")
        
    except Exception as e:
        print(f"Error during database cleanup: {e}")

if __name__ == "__main__":
    clean_timestamps()