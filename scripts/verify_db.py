#!/usr/bin/env python3
"""Verify database was initialized correctly."""
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "/app/dev.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print(f"[VERIFY] Database at {db_path}")
    print(f"[VERIFY] Found {len(tables)} tables:")
    for table in tables:
        print(f"[VERIFY]   - {table[0]}")
    
    # Check for critical tables
    critical_tables = {'games', 'game_settings', 'game_state', 'players'}
    found_tables = {t[0] for t in tables}
    
    missing = critical_tables - found_tables
    if missing:
        print(f"[VERIFY] ✗ CRITICAL: Missing tables: {missing}")
        sys.exit(1)
    else:
        print(f"[VERIFY] ✓ All critical tables present")
        sys.exit(0)
        
except Exception as e:
    print(f"[VERIFY] ✗ Error verifying database: {e}")
    sys.exit(1)
